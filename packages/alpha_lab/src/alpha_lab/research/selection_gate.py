"""Fail-closed selection-aware inference gate for five chronological folds.

Five folds cannot achieve two-sided Bonferroni significance over nine
asset/cost comparisons with an exact sign test (minimum p=0.0625).
No attempt is made to claim independent holdout or adaptively adjusted alpha.
"""
from math import comb

def exact_two_sided_sign_test(positive: int, negative: int) -> float:
    n=positive+negative
    if n == 0:
        return 1.0
    k=min(positive,negative)
    return min(1.0,2*sum(comb(n,j) for j in range(k+1))/2**n)

def selection_aware_gate(reports: list[dict], *, familywise_alpha: float=.05) -> dict:
    if len(reports)!=9 or not 0<familywise_alpha<1:
        raise ValueError("Expected nine predeclared comparisons")
    results=[]
    for item in reports:
        if len(item["folds"])!=5:
            raise ValueError("Expected five independent-reset folds")
        returns=[f["return_pct"] for f in item["folds"]]
        positive=sum(x>0 for x in returns)
        negative=sum(x<0 for x in returns)
        p=exact_two_sided_sign_test(positive,negative)
        results.append({"market":item["market"],"cost_bps":item["cost_bps_fee_and_slippage_each_side"],
                        "positive_folds":positive,"negative_folds":negative,
                        "unadjusted_two_sided_sign_p":p,
                        "bonferroni_nine_comparisons_p":min(1.0,9*p),
                        "statistically_significant":False})
    return {"method":"Exact fold-level two-sided sign test with Bonferroni over nine comparisons",
            "familywise_alpha":familywise_alpha,
            "adaptive_prior_selection_corrected":False,
            "folds_independent_proven":False,
            "statistical_validation":"NOT_ESTABLISHED",
            "promotion_authorised":False,"comparisons":results}
