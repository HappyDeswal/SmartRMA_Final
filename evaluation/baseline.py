"""Read-only current-retriever timing and coverage. No unreviewed accuracy or end-to-end latency claims."""
import argparse,hashlib,json,statistics,time,platform
from pathlib import Path
from node.node2_policy_rag import search_policy_chunks as retrieve_chunks

def run(queries,repeats=5):
    if repeats<1:raise ValueError('repeats must be positive')
    records=[];samples=[]
    for q in queries:
        result=[];timings=[]
        for _ in range(repeats):
            start=time.perf_counter();result=retrieve_chunks(q['query'],top_k=5,target_mfg=q['manufacturer']);timings.append((time.perf_counter()-start)*1000)
        samples+=timings;records.append({'id':q['id'],'ranked_chunk_ids':[r['id'] for r in result],'elapsed_ms':timings})
    ordered=sorted(samples)
    return {'task':'retrieval_only_unreviewed_query_diagnostics','method':'manufacturer_filtered_keyword_search','query_count':len(queries),'repeats_per_query':repeats,'retrieval_mean_ms':statistics.mean(samples),'retrieval_median_ms':statistics.median(samples),'retrieval_p95_ms':ordered[min(len(ordered)-1,int(.95*(len(ordered)-1)))],'queries_with_any_result':sum(bool(r['ranked_chunk_ids']) for r in records),'accuracy':None,'reason':'Human gold labels pending; returning passages does not establish relevance or answer correctness. Timings exclude HTTP, LLM generation, vision, queueing and decision persistence.','python':platform.python_version(),'records':records}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--queries',required=True);p.add_argument('--output',required=True);p.add_argument('--repeats',type=int,default=5);a=p.parse_args();f=Path(a.queries);queries=json.loads(f.read_text());r=run(queries,a.repeats);r['queries_sha256']=hashlib.sha256(f.read_bytes()).hexdigest();r['policy_index_sha256']=hashlib.sha256(Path('policy/policy_index.json').read_bytes()).hexdigest();Path(a.output).parent.mkdir(parents=True,exist_ok=True);Path(a.output).write_text(json.dumps(r,indent=2));print(json.dumps({k:v for k,v in r.items() if k!='records'},indent=2))
