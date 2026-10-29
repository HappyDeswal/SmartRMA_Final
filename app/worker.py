import logging,threading,time
from .models import ModelBusy

log=logging.getLogger('happy.worker')

class Worker:
    def __init__(self,store,models,policies):
        self.store=store;self.models=models;self.policies=policies;self.stop_flag=threading.Event();self.thread=None
    def start(self):
        self.store.recover_jobs();self.thread=threading.Thread(target=self.run,name='happy-inspection-worker',daemon=True);self.thread.start()
    def stop(self):
        self.stop_flag.set()
        if self.thread:self.thread.join(timeout=5)
    def run_once(self):
        job=self.store.claim_job()
        if not job:return False
        try:
            case=self.store.get_case(job['case_id']);observations=[];models=[];deadline=time.monotonic()+240
            for number,photo in enumerate(case['photos'],1):
                if self.stop_flag.is_set():return False # running job is recovered on next startup
                self.store.progress(job['id'],f'Inspecting photo {number} of {len(case["photos"])}')
                raw=self.store.image(photo['id'])['data']
                if time.monotonic()>=deadline:
                    obs=self.models.inconclusive('Total inspection budget exhausted; resubmit evidence.');model=None
                else:obs,model=self.models.inspect(raw,deadline)
                observations.append(obs);models.append(model)
            self.store.progress(job['id'],'Retrieving manufacturer policy advisory')
            policy=self.policies.evaluate(case,observations)
            if self.stop_flag.is_set():return False
            self.store.finalize(job['id'],observations,models,policy)
        except ModelBusy:
            if not self.stop_flag.is_set():self.store.requeue_busy(job['id'])
            self.stop_flag.wait(.5)
        except Exception as exc:
            if self.stop_flag.is_set():return False
            log.error('Inspection job %s failed (%s)',job['id'],type(exc).__name__)
            self.store.fail_job(job['id'],'Processing error: '+type(exc).__name__)
        return True
    def run(self):
        while not self.stop_flag.is_set():
            try:
                if not self.run_once():self.stop_flag.wait(.5)
            except Exception as exc:
                log.error('Worker loop unavailable (%s)',type(exc).__name__);self.stop_flag.wait(2)
