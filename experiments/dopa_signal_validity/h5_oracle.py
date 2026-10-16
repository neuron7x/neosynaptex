"""Separate-process deterministic reward oracle for H5 SOFTWARE simulator.

No network, no model import, no access to test model weights; independent
recomputation of reward contract. Not an independent trusted organization.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


def _object(pairs):
    d={}
    for k,v in pairs:
        if k in d: raise ValueError('duplicate_key')
        d[k]=v
    return d


def certify(path:Path)->dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size>20_000_000:
        raise ValueError('oracle_file_untrusted_or_oversized')
    raw=path.read_bytes()
    if len(raw)>20_000_000:
        raise ValueError('oracle_file_oversized')
    episodes=json.loads(raw,object_pairs_hook=_object,
                        parse_constant=lambda x: (_ for _ in ()).throw(ValueError('nonfinite_json')))
    if not isinstance(episodes,list) or not episodes:
        raise ValueError('invalid_episodes')
    total=0
    for ep in episodes:
        if not isinstance(ep,list) or len(ep)<2:
            raise ValueError('invalid_episode')
        before=None
        for j,st in enumerate(ep):
            if not isinstance(st,dict) or set(st)!={'state','next_state','action','reward','done'}:
                raise ValueError('invalid_step_fields')
            x,n,a,r,done=st['state'],st['next_state'],st['action'],st['reward'],st['done']
            if not (isinstance(x,list) and isinstance(n,list) and len(x)==len(n)==8
                    and type(a) is int and a in (0,1) and type(done) is bool
                    and type(r) in (int,float)):
                raise ValueError('invalid_step_type')
            if any(type(v) not in (int,float) or not math.isfinite(v) for v in [*x,*n,r]):
                raise ValueError('nonfinite_step')
            # Deliberately implemented separately from the generating environment.
            exact=math.sin(n[0]+n[2]*0.5)*0.6 + (n[1]*n[1])*0.5 + (2*a-1)*(x[0]*0.12) - 0.03
            if abs(float(r)-exact)>1e-10:
                raise ValueError('reward_mismatch')
            if done != (j==len(ep)-1):
                raise ValueError('terminal_mismatch')
            if before is not None and any(abs(v-w)>1e-12 for v,w in zip(before,x)):
                raise ValueError('chain_mismatch')
            for item in (x,n):
                if (abs(item[5]-item[0]**2)>1e-10 or abs(item[6]-item[1]*item[2])>1e-10
                        or abs(item[7]-item[3]**2)>1e-10):
                    raise ValueError('derived_feature_mismatch')
            if abs((x[4]-n[4])-1/len(ep))>1e-10:
                raise ValueError('time_progression_mismatch')
            before=n
            total+=1
    return {'contract':'H5_SOFTWARE_ENV_REWARD_ORACLE_v1',
            'status':'CONSISTENT_WITH_DECLARED_REWARD_FUNCTION',
            'trajectory_sha256':hashlib.sha256(raw).hexdigest(),
            'episodes':len(episodes),'transitions':total,
            'authority':'SEPARATE_PROCESS_SAME_SOFTWARE_TRUST_DOMAIN'}


def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument('--input',type=Path,required=True)
    args=p.parse_args()
    print(json.dumps(certify(args.input),sort_keys=True))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
