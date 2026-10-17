import argparse
import json
from config import RESOURCES
from recommendations.apriori import load_baskets
from recommendations.metrics import evaluate
from .evaluate_agents import save

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--support',type=float,default=0.005)
    parser.add_argument('--confidence',type=float,default=0.08)
    parser.add_argument('--lift',type=float,default=1.0)
    args=parser.parse_args()
    result=evaluate(load_baskets(RESOURCES/'Retail.zip'),**vars(args))
    print(json.dumps(save('retail_results.json',result),indent=2))
