"""Small statistical profiles learned only from explicitly vetted local traces."""
from collections import Counter
import hashlib
from .contracts import canonical


def sha(data):
    return hashlib.sha256(canonical(data).encode()).hexdigest()


def fit(traces):
    tokens, transitions = Counter(), Counter()
    totals, lengths = [], []
    for trace in traces:
        previous = 'START'
        for step in trace:
            token = step['operation'] + ':' + step['class']
            tokens[token] += 1
            transitions[previous + '>' + token] += 1
            previous = token
        totals.append(sum(s['bytes'] for s in trace))
        lengths.append(len(trace))
    return {'algorithm':'frequency-transition-v1', 'trace_count':len(traces),
            'tokens':dict(tokens), 'transitions':dict(transitions),
            'max_actions':max(lengths), 'max_bytes':max(totals)}


def score(profile, history, proposed):
    token = proposed['operation'] + ':' + proposed['class']
    previous = history[-1]['operation'] + ':' + history[-1]['class'] if history else 'START'
    pair = previous + '>' + token
    counts = profile['transitions']
    outgoing = sum(v for k,v in counts.items() if k.startswith(previous + '>'))
    # One extra category reserves probability mass for an unseen action class.
    probability = (counts.get(pair,0)+1)/(outgoing+len(profile['tokens'])+1)
    signals=[]
    if token not in profile['tokens']:
        signals.append({'kind':'unseen_action_class','observed':token,'expected':list(profile['tokens'])})
    if probability < 0.15:
        signals.append({'kind':'unlikely_transition','observed':pair,'probability':round(probability,6),'threshold':0.15})
    actions=len(history)+1
    volume=sum(s['bytes'] for s in history)+proposed['bytes']
    if actions>profile['max_actions']:
        signals.append({'kind':'task_length','observed':actions,'training_max':profile['max_actions']})
    if volume>profile['max_bytes']:
        signals.append({'kind':'task_volume','observed':volume,'training_max':profile['max_bytes']})
    return signals, probability
