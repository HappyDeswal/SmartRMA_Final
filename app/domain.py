from decimal import Decimal
from enum import Enum
import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

class Product(str, Enum):
    graphics_card='graphics_card'
    motherboard='motherboard'
    ram='ram'
    ssd='ssd'

class StrictModel(BaseModel):
    model_config=ConfigDict(extra='forbid')

class Intake(StrictModel):
    order_id: str = Field(min_length=1,max_length=64,pattern=r'^[A-Za-z0-9_.-]+$')
    product_type: Product
    product_name: str = Field(min_length=2,max_length=128)
    manufacturer: str = Field('Unknown',min_length=1,max_length=64)
    serial: str = Field('',max_length=128)
    value: Decimal = Field(gt=0,le=100000,max_digits=8,decimal_places=2,allow_inf_nan=False)
    complaint: str = Field(min_length=3,max_length=2000)
    slots: list[int] = Field(min_length=1,max_length=5)

    @field_validator('order_id','product_name','manufacturer','complaint',mode='before')
    @classmethod
    def text(cls,v):
        if not isinstance(v,str) or not v.strip() or not any(ch.isalnum() for ch in v):
            raise ValueError('A nonblank value is required.')
        return v.strip()

    @field_validator('slots')
    @classmethod
    def slots_unique(cls,v):
        if len(set(v))!=len(v) or any(s<0 or s>4 for s in v):
            raise ValueError('Use distinct photo slots from 0 to 4.')
        return v

    @property
    def cents(self): return int(self.value*100)

class HardwareHint(StrictModel):
    product_type: Product
    score: float = Field(ge=0,le=1,allow_inf_nan=False)
    model_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    advisory_only: Literal[True] = True
    score_method: Literal['validation_temperature_scaled_not_condition_confidence'] = 'validation_temperature_scaled_not_condition_confidence'

class Observation(StrictModel):
    hardware_visible: bool
    condition: Literal['clean','physical_damage','cosmetic_wear','tampered','uncertain']
    findings: str = Field(min_length=12,max_length=500)
    confidence: float = Field(ge=0,le=1,allow_inf_nan=False)
    anomaly_score: float = Field(ge=0,le=1,allow_inf_nan=False)
    hardware_hint: HardwareHint | None = None

class Credentials(StrictModel):
    username: str = Field(min_length=3,max_length=64,pattern=r'^[a-zA-Z0-9_.-]+$')
    password: str = Field(min_length=1,max_length=256)

class NewUser(Credentials):
    role: Literal['admin','reviewer','viewer']='reviewer'
    @field_validator('password')
    @classmethod
    def strong(cls,v):
        if len(v)<12: raise ValueError('Use at least 12 characters.')
        return v

class PasswordChange(StrictModel):
    current_password: str = Field(min_length=1,max_length=256)
    new_password: str = Field(min_length=12,max_length=256)

class HumanDecision(StrictModel):
    decision: Literal['approved','rejected']
    reason: str = Field(min_length=12,max_length=2000)
    revision: int = Field(ge=1)
    @field_validator('reason')
    @classmethod
    def reason_text(cls,v):
        if len(v.strip())<12: raise ValueError('Explain the actual review findings.')
        return v.strip()

class ChatInput(StrictModel):
    message: str = Field(min_length=1,max_length=2000)
    manufacturer: str = Field('Unknown',max_length=64)
    product_type: Product = Product.graphics_card
    history: list[dict] = Field(default_factory=list,max_length=8)
    @field_validator('history')
    @classmethod
    def history_bound(cls,v):
        if any(set(m)!={'role','content'} or m['role'] not in {'user','assistant'} or not isinstance(m['content'],str) or len(m['content'])>2000 for m in v):
            raise ValueError('Invalid bounded conversation history.')
        return v

class PhotoQuestion(StrictModel):
    image_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    question: str = Field(min_length=3,max_length=1000)

REASONS={
 'PRICE_REQUIRES_HUMAN':'Value exceeds $2,500; a human must decide.',
 'CLEAN_PASSES_RULES':'Clean assessed photos meet the risk and tier confidence rules.',
 'INSPECTION_UNAVAILABLE':'Inspection was inconclusive or unavailable; retry with sufficient evidence.',
 'CONFLICTING_EVIDENCE':'Visual findings and anomaly estimates conflict; resubmit evidence.',
 'VISIBLE_DAMAGE':'AI reported visible physical damage or tampering.',
 'COSMETIC_WEAR':'AI reported visible cosmetic wear.',
 'LOW_CONFIDENCE':'Condition confidence is below this tier’s approval threshold; resubmit evidence.',
 'HIGH_RISK':'Risk is too high for automatic approval.',
 'SIMILAR_PHOTO':'A similar image exists on another order; provide new evidence.',
 'EDITING_METADATA':'Editing software metadata is present; provide original evidence.',
 'POLICY_EXCLUSION':'An indexed manufacturer exclusion supports rejection.',
}

def tier(cents):
    return 'T1' if cents<30000 else 'T2' if cents<=100000 else 'T3' if cents<=250000 else 'T4'

def aggregate(observations):
    available=bool(observations) and all(o.hardware_visible and o.condition!='uncertain' for o in observations)
    conditions=sorted({o.condition for o in observations})
    conflicts=[i for i,o in enumerate(observations) if (o.condition=='clean' and o.anomaly_score>=.3) or (o.condition in {'physical_damage','tampered'} and o.anomaly_score<.3)]
    return {'available':available,'conditions':conditions,'consistent':not conflicts,'conflicting_views':conflicts,
            'confidence':min((o.confidence for o in observations),default=0) if available else 0,
            'anomaly_score':max((o.anomaly_score for o in observations),default=.5) if available else None,
            'identity_status':'not_verified','confidence_method':'model_estimate_not_calibrated'}

def decide(cents,evidence,policy,similar=False,edited=False):
    level=tier(cents)
    score=evidence.get('anomaly_score')
    risk=None if score is None else min(100,round(score*70+(20 if policy.get('grounded') and policy.get('excluded') else 0)+(30 if similar or edited else 0)))
    if level=='T4':
        return {'status':'needs_review','tier':level,'risk':risk,'human_required':True,'source':'automatic',
                'reason_codes':['PRICE_REQUIRES_HUMAN'],'reasons':[REASONS['PRICE_REQUIRES_HUMAN']],'rejection_kind':None}
    reasons=[]
    if similar: reasons.append('SIMILAR_PHOTO')
    if edited: reasons.append('EDITING_METADATA')
    if not evidence.get('available'): reasons.append('INSPECTION_UNAVAILABLE')
    if not evidence.get('consistent'): reasons.append('CONFLICTING_EVIDENCE')
    if policy.get('grounded') and policy.get('excluded'): reasons.append('POLICY_EXCLUSION')
    conditions=set(evidence.get('conditions',[]))
    if conditions & {'physical_damage','tampered'}: reasons.append('VISIBLE_DAMAGE')
    elif 'cosmetic_wear' in conditions: reasons.append('COSMETIC_WEAR')
    if evidence.get('confidence',0)<(.95 if level=='T3' else .85): reasons.append('LOW_CONFIDENCE')
    if risk is not None and risk>=30: reasons.append('HIGH_RISK')
    if conditions!={'clean'} and not reasons: reasons.append('INSPECTION_UNAVAILABLE')
    approved=not reasons
    if approved: reasons=['CLEAN_PASSES_RULES']
    return {'status':'approved' if approved else 'rejected','tier':level,'risk':risk,'human_required':False,
            'source':'automatic','reason_codes':reasons,'reasons':[REASONS[r] for r in reasons],
            'rejection_kind':None if approved else 'visible_condition' if conditions & {'physical_damage','tampered','cosmetic_wear'} and evidence.get('available') and evidence.get('consistent') else 'resubmit_evidence'}
