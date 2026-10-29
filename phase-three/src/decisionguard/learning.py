"""Owner-controlled trace curation, baseline versions and durable explanations."""
import json
from .behavior import fit, score, sha
from .contracts import GuardError, identifier, integer, require
from .storage import owner_uid


class Learning:
    def label(self, resource_id, version, resource_class, impact):
        identifier(resource_id); identifier(resource_class); integer(version); integer(impact)
        require(impact<=5, 'Impact must be 1–5.')
        with self.store.transaction() as db:
            require(db.execute('SELECT 1 FROM resources WHERE resource_id=? AND version=?',(resource_id,version)).fetchone() is not None,'Import the resource first.')
            require(db.execute('SELECT 1 FROM labels WHERE resource_id=? AND version=?',(resource_id,version)).fetchone() is None,'Labels are immutable; reimport and explicitly approve a new resource version to change them.')
            db.execute('INSERT INTO labels VALUES(?,?,?,?)',(resource_id,version,resource_class,impact))
            self._event(db,'resource_labeled',resource_id,{'version':version,'class':resource_class,'impact':impact})
            return {'resource_id':resource_id,'version':version,'class':resource_class,'impact':impact}

    def _history(self, db, task_id):
        result=[]
        # Completion-event sequence is authoritative, including equal timestamps.
        for row in db.execute("SELECT a.body,r.byte_count FROM events e JOIN actions a ON a.request_id=e.subject JOIN receipts r ON r.request_id=a.request_id WHERE e.kind='action_completed' ORDER BY e.sequence"):
            action=json.loads(row['body'])
            if action['task_id']!=task_id:
                continue
            label=db.execute('SELECT class FROM labels WHERE resource_id=? AND version=?',(action['resource_id'],action['resource_version'])).fetchone()
            result.append({'operation':action['operation'],'class':label[0] if label else 'unlabeled','bytes':row['byte_count']})
        return result

    def approve_trace(self, trace_id, task_id, split, reason):
        identifier(trace_id); identifier(task_id)
        require(split in ('train','validation','test'),'Choose train, validation or test.')
        require(isinstance(reason,str) and 0<len(reason)<=500,'An owner review reason is required.')
        with self.store.transaction() as db:
            require(db.execute('SELECT 1 FROM traces WHERE trace_id=?',(trace_id,)).fetchone() is None,'Trace ID already exists.')
            steps=self._history(db,task_id)
            require(bool(steps),'A trace needs completed actions.')
            require(all(s['class']!='unlabeled' for s in steps),'Label every consumed resource before curating a trace.')
            body={'task_id':task_id,'steps':steps}
            # Prevent the same source task being relabeled into multiple data partitions.
            for row in db.execute('SELECT body FROM traces'):
                require(json.loads(row[0])['task_id']!=task_id,'This task already has a frozen trace.')
            from .contracts import canonical
            db.execute('INSERT INTO traces VALUES(?,?,?,?,?,?)',(trace_id,split,canonical(body),sha(body),reason,owner_uid()))
            self._event(db,'trace_approved',trace_id,{'split':split,'source_task':task_id,'sha256':sha(body),'reason':reason})
            return {'trace_id':trace_id,'split':split,'sha256':sha(body),'actions':len(steps)}

    def train(self, task_id, trace_ids):
        identifier(task_id)
        require(isinstance(trace_ids,list) and len(trace_ids)>=3 and len(set(trace_ids))==len(trace_ids),'Supply at least three distinct training traces.')
        with self.store.transaction() as db:
            task=db.execute('SELECT current_version FROM tasks WHERE task_id=?',(task_id,)).fetchone()
            require(task is not None,'Approve the target task first.')
            traces=[]; provenance=[]
            for trace_id in trace_ids:
                identifier(trace_id)
                row=db.execute('SELECT * FROM traces WHERE trace_id=?',(trace_id,)).fetchone()
                require(row is not None and row['split']=='train','Only owner-approved training traces may fit a profile.')
                body=json.loads(row['body'])
                require(body['task_id']!=task_id,'Target task must be separate from training tasks.')
                require(sha(body)==row['digest'],'Trace integrity mismatch.')
                traces.append(body['steps']); provenance.append({'trace_id':trace_id,'sha256':row['digest']})
            profile=fit(traces)
            profile['training_sources']=provenance
            profile['dataset_sha256']=sha(provenance)
            version=db.execute('SELECT coalesce(max(version),0)+1 FROM profiles WHERE task_id=?',(task_id,)).fetchone()[0]
            from .contracts import canonical
            db.execute('INSERT INTO profiles VALUES(?,?,?,?,?)',(task_id,version,task[0],canonical(profile),sha(profile)))
            self._event(db,'profile_trained',task_id,{'version':version,'scope_version':task[0],'dataset_sha256':profile['dataset_sha256']})
            return {'task_id':task_id,'version':version,'scope_version':task[0],**profile}

    def _behavior(self,db,action,hard_reason,scope_version,cost):
        label=db.execute('SELECT * FROM labels WHERE resource_id=? AND version=?',(action.resource_id,action.resource_version)).fetchone()
        impact=label['impact'] if label else None
        row=db.execute('SELECT * FROM profiles WHERE task_id=? ORDER BY version DESC LIMIT 1',(action.task_id,)).fetchone()
        status='cold_start'; signals=[]; version=None; probability=None; dataset=None; count=0
        if row:
            version=row['version']
            profile=json.loads(row['body'])
            require(sha(profile)==row['digest'],'Profile integrity mismatch; execution stopped.')
            dataset=profile['dataset_sha256']; count=profile['trace_count']
            status='stale_profile' if row['scope_version']!=scope_version else 'active'
            if status=='active' and label:
                signals,probability=score(profile,self._history(db,action.task_id),{'operation':action.operation,'class':label['class'],'bytes':cost})
        if not label:
            status='unlabeled'
        severity=3 if hard_reason!='authorized' else (2 if len(signals)>=2 else 1 if signals else 0)
        hold=hard_reason=='authorized' and action.operation=='write_note' and (len(signals)>=2 or status in ('stale_profile','unlabeled'))
        return {'baseline_status':status,'profile_version':version,'dataset_sha256':dataset,
                'scope_version':scope_version,'signals':signals,'transition_probability':probability,
                'evidence_severity':severity,'impact':impact,'risk_priority':severity*impact*5 if impact else None,
                'risk_meaning':'engineering triage, not probability of compromise',
                'hard_policy_reason':hard_reason,'hold_required':hold,
                'training_trace_count':count,'limited_training':count<20,
                'uncertainty':'No personal history is inferred; profiles use explicitly approved task traces.'}

    def review(self,request_id,reason):
        identifier(request_id)
        require(isinstance(reason,str) and 0<len(reason)<=500,'Supply a review reason.')
        with self.store.transaction() as db:
            row=db.execute('SELECT * FROM actions WHERE request_id=?',(request_id,)).fetchone()
            require(row is not None and row['status']=='queued' and row['reason']=='behavior_review','Only held work can be reviewed.')
            from .contracts import Action
            action=Action.from_dict(json.loads(row['body']))
            hard,scope,cost=self._assess(db,action,row['principal'])
            require(hard=='authorized','Current hard policy denies this action; review cannot override it.')
            evidence=self._behavior(db,action,hard,scope,cost)
            require(evidence['baseline_status']=='active','Label resources and train a current profile before releasing held work.')
            db.execute('INSERT OR REPLACE INTO reviews VALUES(?,?,?,?)',(request_id,evidence['profile_version'],scope,reason))
            self._event(db,'behavior_reviewed',request_id,{'profile_version':evidence['profile_version'],'scope_version':scope,'reason':reason})
            return {'request_id':request_id,'reviewed':True,'note':'Dispatch still rechecks current authority and profile.'}

    def evaluate_profile(self,task_id,trace_ids):
        with self.store.transaction() as db:
            row=db.execute('SELECT * FROM profiles WHERE task_id=? ORDER BY version DESC LIMIT 1',(task_id,)).fetchone()
            require(row is not None,'Train a profile first.')
            profile=json.loads(row['body']); require(sha(profile)==row['digest'],'Profile integrity mismatch.')
            reports=[]
            require(bool(trace_ids) and len(set(trace_ids))==len(trace_ids),'Supply distinct held-out traces.')
            for trace_id in trace_ids:
                trace=db.execute('SELECT * FROM traces WHERE trace_id=?',(trace_id,)).fetchone()
                require(trace is not None and trace['split'] in ('validation','test'),'Evaluation must use held-out traces.')
                body=json.loads(trace['body']); require(sha(body)==trace['digest'],'Trace integrity mismatch.')
                history=[]; flagged=0; holds=0
                for step in body['steps']:
                    signals,_=score(profile,history,step)
                    flagged+=bool(signals); holds+=step['operation']=='write_note' and len(signals)>=2
                    history.append(step)
                reports.append({'trace_id':trace_id,'split':trace['split'],'actions':len(history),'flagged_actions':flagged,'hypothetical_holds':holds})
            return {'profile_version':row['version'],'dataset_sha256':profile['dataset_sha256'],'traces':reports,
                    'note':'Offline replay of owner-vetted benign traces; holds are false holds here, not measured attack prevention.'}
