"""Metrics on explicit ground truth and predictions, with validation and tied-score handling."""
import math

def classification(labels, truth, predicted):
    if not labels or len(set(labels))!=len(labels) or not truth or len(truth)!=len(predicted):
        raise ValueError('Need unique labels and equal, nonempty truth/prediction sequences')
    index={v:i for i,v in enumerate(labels)};matrix=[[0]*len(labels) for _ in labels]
    for a,b in zip(truth,predicted):
        if a not in index or b not in index:raise ValueError('Unknown class')
        matrix[index[a]][index[b]]+=1
    rows=[]
    for i,label in enumerate(labels):
        tp=matrix[i][i];support=sum(matrix[i]);count=sum(r[i] for r in matrix)
        precision=tp/count if count else 0;recall=tp/support if support else 0
        rows.append({'label':label,'support':support,'precision':precision,'recall':recall,'f1':2*precision*recall/(precision+recall) if precision+recall else 0})
    return {'n':len(truth),'accuracy':sum(matrix[i][i] for i in range(len(labels)))/len(truth),'macro_f1':sum(r['f1'] for r in rows)/len(labels),'labels':labels,'confusion_matrix':matrix,'per_class':rows,'missing_classes':[r['label'] for r in rows if not r['support']]}

def binary_ranking(truth,scores):
    if not truth or len(truth)!=len(scores) or any(v not in (0,1) for v in truth) or any(not math.isfinite(v) for v in scores):raise ValueError('Invalid binary scores')
    positives=sum(truth);negatives=len(truth)-positives
    if not positives or not negatives:raise ValueError('Both positive and negative examples required')
    groups={}
    for t,s in zip(truth,scores):groups.setdefault(s,[]).append(t)
    tp=fp=0;previous_tpr=previous_fpr=0;auc=ap=0;roc=[[0,0]];pr=[[0,1]]
    for score,values in sorted(groups.items(),reverse=True):
        tp+=sum(values);fp+=len(values)-sum(values);tpr=tp/positives;fpr=fp/negatives;precision=tp/(tp+fp)
        auc+=(fpr-previous_fpr)*(tpr+previous_tpr)/2;ap+=(tpr-previous_tpr)*precision
        roc.append([fpr,tpr]);pr.append([tpr,precision]);previous_fpr=fpr;previous_tpr=tpr
    return {'roc_auc':auc,'average_precision':ap,'roc':roc,'precision_recall':pr}

def retrieval(queries,rankings):
    if not queries:raise ValueError('Empty evaluation')
    ids=[q['id'] for q in queries]
    if len(set(ids))!=len(ids) or set(rankings)!=set(ids):raise ValueError('Rankings must match all unique query IDs exactly')
    reciprocal=top1=top3=0;abstentions=0;answerable=0
    for q in queries:
        if q.get('review_state')!='approved' or not q.get('reviewer') or not isinstance(q.get('answerable'),bool):raise ValueError('Human-approved labels and answerability required')
        gold=set(q['relevant_chunk_ids']);rank=rankings[q['id']]
        if len(set(rank))!=len(rank):raise ValueError('Duplicate retrieved IDs')
        if q['answerable']:
            if not gold:raise ValueError('Answerable query needs relevant chunks')
            answerable+=1;hits=[i+1 for i,x in enumerate(rank) if x in gold]
            if hits:reciprocal+=1/hits[0];top1+=hits[0]==1;top3+=hits[0]<=3
        else:
            if gold:raise ValueError('Unanswerable query cannot have gold passages')
            abstentions+=not rank
    return {'n':len(queries),'answerable_n':answerable,'top1':top1/answerable if answerable else None,'top3':top3/answerable if answerable else None,'mrr':reciprocal/answerable if answerable else None,'unanswerable_n':len(queries)-answerable,'correct_abstentions':abstentions}
