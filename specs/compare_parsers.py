import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ddd_parser import TachoParser
from core.deterministic_parser import DeterministicParser

def compare():
    path = "DDD/D_20250715_1849_Milan_Adalberto_I100000168598002.ddd"
    if not os.path.exists(path):
        print("File not found")
        return
    with open(path, "rb") as f:
        data = f.read()
    
    # 1. Old parser
    print("--- OLD PARSER ---")
    old_parser = TachoParser(path)
    # We must make sure it uses the old parser path
    old_parser.use_deterministic = False 
    old_res = old_parser.parse()
    print("Old Gen:", old_res["metadata"]["generation"])
    print("Old Driver:", old_res.get("driver"))
    print("Old Activities count:", len(old_res.get("activities", [])))
    print("Old raw_tags keys count:", len(old_res.get("raw_tags", {})))
    print("First 15 old raw_tags keys:")
    for k in sorted(old_res.get("raw_tags", {}).keys())[:15]:
        print(f"  {k}")
        
    # 2. Deterministic parser
    print("\n--- DETERMINISTIC PARSER ---")
    dp = DeterministicParser(parser=old_parser)
    new_res = dp.parse(data, is_vu=False)
    print("New Gen:", new_res["metadata"]["generation"])
    print("New Driver:", new_res.get("driver"))
    print("New Activities count:", len(new_res.get("activities", [])))
    print("New raw_tags keys count:", len(new_res.get("raw_tags", {})))
    print("First 15 new raw_tags keys:")
    for k in sorted(new_res.get("raw_tags", {}).keys())[:15]:
        print(f"  {k}")

if __name__ == "__main__":
    compare()
