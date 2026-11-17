import sys,unittest,itertools,random
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from build_v096_stage10_nationality import assign,reciprocal,relocate,record,edits_for,R,EN,EA,SELECT_LEN
from audit_v096_nationality_refs import refs
class Nationality(unittest.TestCase):
    def test_exhaustive_optimal(self):
        rng=random.Random(26)
        for n in range(1,7):
            for _ in range(30):
                rs=[(rng.randrange(3),22+i) for i in range(n)]
                targets={a:rng.randrange(3) for a in rs}
                plan=assign(set(rs),targets)
                best=max(sum(b[0]==targets[a] for a,b in zip(rs,perm)) for perm in itertools.permutations(rs))
                self.assertEqual(sum(plan[a][0]==targets[a] for a in rs),best)
                self.assertEqual(set(plan.values()),set(rs))
                for a in rs:
                    if a[0]==targets[a]:self.assertEqual(plan[a],a)
    def fixture(self):
        sel=bytearray(SELECT_LEN)
        aa=[(i//22,i%22) for i in range(526)]+[(30,22),(31,22)]
        for i,r in enumerate(aa):sel[R+2*i:R+2*i+2]=bytes(r)
        native={(30,22):0,(31,22):1}
        for idx in range(2):
            sel[EN+10*idx:EN+10*idx+10]=bytes([65+idx])*10
            sel[EA+12*idx:EA+12*idx+12]=bytes(range(idx,idx+12))
        return sel,native
    def test_record_preserved(self):
        s,n=self.fixture();a,b=n
        p=reciprocal(set(n),{a:b[0],b:a[0]})
        z=relocate(s,n,p)
        self.assertEqual(record(s,0),record(z,1))
        self.assertEqual(record(s,1),record(z,0))
        self.assertEqual(refs(z)[-2:],[b,a])
        self.assertEqual(refs(s)[:-2],refs(z)[:-2])
        self.assertEqual(len(edits_for(s,z)),3)
    def test_reject_nonpermutation(self):
        s,n=self.fixture();a,b=n
        with self.assertRaises(ValueError):relocate(s,n,{a:b})
    def test_reject_no_reciprocal(self):
        a,b=(1,22),(2,22)
        with self.assertRaises(ValueError):reciprocal({a,b},{a:3,b:1})
if __name__=="__main__":unittest.main()
