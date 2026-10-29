"""Trusted-runner dependency capture and conservative quarantine."""
import json
from .contracts import Action, Scope, Permission, canonical, exact, identifier, integer, require


class Containment:
    def manage(self, task_id):
        identifier(task_id)
        with self.store.transaction() as db:
            require(db.execute('SELECT 1 FROM tasks WHERE task_id=?',(task_id,)).fetchone() is not None,'Approve the task first.')
            for row in db.execute('SELECT body FROM actions'):
                require(json.loads(row[0])['task_id']!=task_id,'Enroll before submitting any actions; existing history cannot be declared clean.')
            db.execute('INSERT OR IGNORE INTO managed_tasks VALUES(?)',(task_id,))
            self._event(db,'task_managed',task_id,{})
            return {'task_id':task_id,'managed':True}

    def _context(self,db,grant_id):
        return db.execute('SELECT * FROM contexts WHERE grant_id=?',(grant_id,)).fetchone()

    def _node(self,context):
        return f"c:{context['context_id']}:{context['revision']}"

    def _edge(self,db,source,target):
        db.execute('INSERT OR IGNORE INTO edges VALUES(?,?)',(source,target))

    def _advance(self,db,context,source=None):
        old=self._node(context); revision=context['revision']+1
        new=f"c:{context['context_id']}:{revision}"
        db.execute('INSERT INTO nodes VALUES(?,?,0)',(new,context['context_id']))
        self._edge(db,old,new)
        if source:
            self._edge(db,source,new)
        # Shared mutable memory makes both contexts dependent on each other.
        for peer in db.execute('SELECT * FROM contexts WHERE memory_id=? AND context_id!=?',(context['memory_id'],context['context_id'])):
            self._edge(db,self._node(peer),new)
            self._edge(db,new,self._node(peer))
        db.execute('UPDATE contexts SET revision=? WHERE context_id=?',(revision,context['context_id']))
        return new

    def open_context(self,context_id,grant_id,memory_id):
        for value in (context_id,grant_id,memory_id): identifier(value)
        with self.store.transaction() as db:
            grant=db.execute('SELECT * FROM grants WHERE grant_id=?',(grant_id,)).fetchone()
            require(grant is not None and not grant['revoked'] and grant['expires_at']>self.clock(),'Use a live grant.')
            require(db.execute('SELECT 1 FROM managed_tasks WHERE task_id=?',(grant['task_id'],)).fetchone() is not None,'Enroll the task first.')
            require(db.execute('SELECT 1 FROM contexts WHERE context_id=? OR grant_id=?',(context_id,grant_id)).fetchone() is None,'Context or grant already registered.')
            require(db.execute('SELECT 1 FROM contexts WHERE memory_id=? AND quarantined=1',(memory_id,)).fetchone() is None,'Memory is quarantined; use a genuinely fresh isolated memory.')
            db.execute('INSERT INTO contexts VALUES(?,?,?,0,0)',(context_id,grant_id,memory_id))
            node=f'c:{context_id}:0';db.execute('INSERT INTO nodes VALUES(?,?,0)',(node,context_id))
            for peer in db.execute('SELECT * FROM contexts WHERE memory_id=? AND context_id!=?',(memory_id,context_id)):
                self._edge(db,node,self._node(peer));self._edge(db,self._node(peer),node)
            link=db.execute('SELECT parent FROM delegations WHERE child=?',(grant_id,)).fetchone()
            if link:
                parent=self._context(db,link[0]);require(parent is not None and not parent['quarantined'],'Parent context is unavailable.')
                self._edge(db,self._node(parent),node)
            self._event(db,'context_opened' ,context_id,{'grant_id':grant_id,'memory_id':memory_id})
            return {'context_id':context_id,'node_id':node}

    def _managed_check(self,db,action):
        if not db.execute('SELECT 1 FROM managed_tasks WHERE task_id=?',(action.task_id,)).fetchone():
            return 'authorized'
        context=self._context(db,action.grant_id)
        if context is None: return 'missing_context'
        if context['quarantined']: return 'context_quarantined'
        current=action.grant_id; seen=set()
        while True:
            if current in seen: return 'delegation_cycle'
            seen.add(current)
            link=db.execute('SELECT * FROM delegations WHERE child=?',(current,)).fetchone()
            if link is None: break
            if {'operation':action.operation,'resource_id':action.resource_id,'resource_version':action.resource_version} not in json.loads(link['permissions']):
                return 'delegated_scope_violation'
            parent=db.execute('SELECT * FROM grants WHERE grant_id=?',(link['parent'],)).fetchone()
            task=db.execute('SELECT current_version FROM tasks WHERE task_id=?',(action.task_id,)).fetchone()
            if parent is None or parent['revoked'] or parent['expires_at']<=self.clock() or parent['scope_version']!=task[0]:
                return 'ancestor_invalid'
            current=link['parent']
        # Inspect all recorded ancestors of the current context snapshot.
        pending=[self._node(context)];seen=set()
        while pending:
            node=pending.pop()
            if node in seen: continue
            seen.add(node)
            row=db.execute('SELECT quarantined FROM nodes WHERE node_id=?',(node,)).fetchone()
            if row is None or row[0]: return 'unclean_dependency'
            pending.extend(r[0] for r in db.execute('SELECT source FROM edges WHERE target=?',(node,)))
        return 'authorized'

    def delegate(self,parent_id,child_id,principal,permissions,ttl):
        for value in (parent_id,child_id,principal): identifier(value)
        integer(ttl);require(ttl<=31536000,'TTL exceeds one year.')
        require(isinstance(permissions,list) and bool(permissions),'Supply a nonempty permission list.')
        require(len(permissions)<=100,'At most 100 permissions are supported.')
        for p in permissions:exact(p,{'operation','resource_id','resource_version'})
        parsed=[Permission(**p) for p in permissions]
        require(len(set(parsed))==len(parsed),'Duplicate delegated permissions are not allowed.')
        with self.store.transaction() as db:
            parent=db.execute('SELECT * FROM grants WHERE grant_id=?',(parent_id,)).fetchone()
            context=self._context(db,parent_id)
            require(parent is not None and context is not None and not context['quarantined'],'A managed parent context is required.')
            for permission in parsed:
                check=Action('delegation-check',parent['task_id'],parent_id,permission.operation,permission.resource_id,permission.resource_version,'delegation' if permission.operation=='write_note' else '')
                reason,_,_=self._assess(db,check,parent['principal'])
                require(reason=='authorized','Child permissions must fit live parent authority and current limits.')
            require(self.clock()+ttl<=parent['expires_at'],'Child expiry cannot exceed parent expiry.')
            require(db.execute('SELECT 1 FROM grants WHERE grant_id=?',(child_id,)).fetchone() is None,'Child grant already exists.')
            db.execute('INSERT INTO grants(grant_id,principal,task_id,scope_version,expires_at) VALUES(?,?,?,?,?)',
                       (child_id,principal,parent['task_id'],parent['scope_version'],self.clock()+ttl))
            db.execute('INSERT INTO delegations VALUES(?,?,?)',(child_id,parent_id,canonical(permissions)))
            self._event(db,'grant_delegated',child_id,{'parent':parent_id,'principal':principal})
            return {'grant_id':child_id,'parent':parent_id,'requires_context':True}

    def _quarantine(self,db,context_id,reason,unknown=False):
        root=db.execute('SELECT * FROM contexts WHERE context_id=?',(context_id,)).fetchone()
        require(root is not None,'Unknown context.')
        affected={context_id}
        if unknown:
            task=db.execute('SELECT task_id FROM grants WHERE grant_id=?',(root['grant_id'],)).fetchone()[0]
            affected.update(r[0] for r in db.execute('SELECT c.context_id FROM contexts c JOIN grants g ON g.grant_id=c.grant_id WHERE g.task_id=?',(task,)))
        changed=True
        while changed:
            before=set(affected)
            seeds=[r[0] for c in affected for r in db.execute('SELECT node_id FROM nodes WHERE context_id=?',(c,))]
            visited=set()
            while seeds:
                node=seeds.pop()
                if node in visited:continue
                visited.add(node)
                row=db.execute('SELECT context_id FROM nodes WHERE node_id=?',(node,)).fetchone()
                if row and row[0]:affected.add(row[0])
                seeds.extend(r[0] for r in db.execute('SELECT target FROM edges WHERE source=?',(node,)))
            grants={r[0] for c in affected for r in db.execute('SELECT grant_id FROM contexts WHERE context_id=?',(c,))}
            # Cascading revocation includes delegated grants with no opened context yet.
            grow=True
            while grow:
                old=set(grants)
                grants.update(r['child'] for r in db.execute('SELECT * FROM delegations') if r['parent'] in grants)
                grow=grants!=old
            affected.update(r[0] for g in grants for r in db.execute('SELECT context_id FROM contexts WHERE grant_id=?',(g,)))
            changed=affected!=before
        for c in affected:
            db.execute('UPDATE contexts SET quarantined=1 WHERE context_id=?',(c,))
            db.execute('UPDATE nodes SET quarantined=1 WHERE context_id=?',(c,))
        for node in visited:db.execute('UPDATE nodes SET quarantined=1 WHERE node_id=?',(node,))
        for g in grants: db.execute('UPDATE grants SET revoked=1 WHERE grant_id=?',(g,))
        for row in db.execute("SELECT request_id,body FROM actions WHERE status='queued'").fetchall():
            if json.loads(row['body'])['grant_id'] in grants:
                db.execute("UPDATE actions SET status='cancelled',reason='contained',updated_at=? WHERE request_id=?",(self.clock(),row['request_id']))
        self._event(db,'contexts_contained',context_id,{'reason':reason,'unknown_lineage':unknown,'contexts':sorted(affected),'grants':sorted(grants)})
        return {'contexts':sorted(affected),'revoked_grants':sorted(grants),'reason':reason}

    def contain(self,context_id,reason,unknown=False):
        identifier(context_id);require(isinstance(reason,str) and 0<len(reason)<=500,'Supply a containment reason.')
        with self.store.transaction() as db:return self._quarantine(db,context_id,reason,unknown)

    def consume(self,context_id,output_id):
        identifier(context_id);identifier(output_id)
        with self.store.transaction() as db:
            context=db.execute('SELECT * FROM contexts WHERE context_id=?',(context_id,)).fetchone()
            require(context is not None and not context['quarantined'],'Use a clean registered context.')
            node='o:'+output_id
            source=db.execute('SELECT * FROM nodes WHERE node_id=?',(node,)).fetchone()
            if source is None:
                return self._quarantine(db,context_id,'missing_output_provenance',True)
            if source['quarantined']:
                return self._quarantine(db,context_id,'attempted_quarantined_consumption')
            # Consumption transfers data, not authority: recipient must independently be authorized for the source resource.
            original=db.execute('SELECT body FROM actions WHERE request_id=?',(output_id,)).fetchone()
            grant=db.execute('SELECT * FROM grants WHERE grant_id=?',(context['grant_id'],)).fetchone()
            origin=Action.from_dict(json.loads(original[0]))
            check=Action('consume-check',grant['task_id'],grant['grant_id'],'read_file',origin.resource_id,origin.resource_version)
            reason,_,cost=self._assess(db,check,grant['principal'])
            require(reason=='authorized','Recipient lacks current authority to consume this resource.')
            self._advance(db,context,node)
            db.execute('UPDATE tasks SET used_actions=used_actions+1,used_bytes=used_bytes+? WHERE task_id=?',(cost,grant['task_id']))
            label=db.execute('SELECT class FROM labels WHERE resource_id=? AND version=?',(origin.resource_id,origin.resource_version)).fetchone()
            self._event(db,'output_consumed',context_id,{'output_id':output_id,'task_id':grant['task_id'],'operation':'read_file','class':label[0] if label else 'unlabeled','bytes':cost})
            return {'context_id':context_id,'output_id':output_id,'output':json.loads(db.execute('SELECT body FROM output_data WHERE node_id=?',(node,)).fetchone()[0])}

    def _capture(self,db,action,output):
        context=self._context(db,action.grant_id)
        if context is None:return
        resource=f'r:{action.resource_id}:{action.resource_version}'
        db.execute('INSERT OR IGNORE INTO nodes VALUES(?,NULL,0)',(resource,))
        current=self._advance(db,context,resource)
        node='o:'+action.request_id
        db.execute('INSERT INTO nodes VALUES(?,?,0)',(node,context['context_id']))
        self._edge(db,current,node)
        db.execute('INSERT INTO output_data VALUES(?,?)',(node,canonical(output)))

    def graph(self):
        with self.store.transaction() as db:
            return {table:[dict(r) for r in db.execute('SELECT * FROM '+table)] for table in ('contexts','nodes','edges','delegations')}

    def _ancestors(self,db,node):
        pending=[node];seen=set()
        while pending:
            current=pending.pop()
            if current in seen:continue
            seen.add(current)
            pending.extend(r[0] for r in db.execute('SELECT source FROM edges WHERE target=?',(current,)))
        return sorted(seen)

    def continuation(self,request_id):
        identifier(request_id)
        with self.store.transaction() as db:
            row=db.execute('SELECT * FROM actions WHERE request_id=?',(request_id,)).fetchone()
            require(row is not None,'Unknown request.')
            action=Action.from_dict(json.loads(row['body']))
            context=self._context(db,action.grant_id)
            require(context is not None,'Unmanaged actions cannot claim checked continuation.')
            reason,version,cost=self._assess(db,action,row['principal'])
            behavior=self._behavior(db,action,reason,version,cost)
            result={'request_id':request_id,'eligible':row['status']=='queued' and reason=='authorized' and not behavior['hold_required'],
                    'reason':reason,'behavior':behavior,'context_revision':context['revision'],
                    'checked_nodes':self._ancestors(db,self._node(context)),
                    'note':'Read-only evidence, not a reusable permit. Dispatch rechecks all state.'}
            self._event(db,'continuation_checked',request_id,result)
            return result
