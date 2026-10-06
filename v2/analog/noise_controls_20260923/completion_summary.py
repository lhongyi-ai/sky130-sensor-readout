"""Spectre completion text is singular for one warning/error; process status is separate."""
import re

def parse_completion(log):
    values=re.findall(r'^spectre completes with (\d+) errors?, (\d+) warnings?(?:,|\.|$)',log,re.I|re.M)
    return {'errors':int(values[-1][0]),'warnings':int(values[-1][1])} if values else None

def execution_completed(exit_code,log):
    summary=parse_completion(log)
    return exit_code==0 and summary is not None and summary['errors']==0
