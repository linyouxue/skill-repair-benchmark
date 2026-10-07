import json

with open('/root/DATA/products/CoachForce.json') as f:
    data = json.load(f)

for doc in data.get('documents', []):
    if doc.get('id') == 'latest_cofoaix_market_research_report':
        print("DOC KEYS:", doc.keys())
        for k in ['reviewers', 'key_reviewers', 'approvers', 'requested_reviewers', 'feedback']:
            if k in doc:
                print(f"DOC {k}:", doc[k])

for pr in data.get('prs', []):
    if 'latest_cofoaix_market_research_report' in json.dumps(pr):
        print("PR KEYS:", pr.keys())
        for k in ['reviewers', 'key_reviewers', 'approvers', 'requested_reviewers']:
            if k in pr:
                print(f"PR {k}:", pr[k])

print("MEETING TRANSCRIPTS:")
for transcript in data.get('meeting_transcripts', []):
    if 'latest_cofoaix_market_research_report' in json.dumps(transcript) or 'Market Research' in json.dumps(transcript):
        print("TRANSCRIPT:", transcript.get('id'), transcript.get('topic'))

print("SLACK:")
for channel, messages in data.get('slack', {}).items():
    for msg in messages:
        if 'latest_cofoaix_market_research_report' in json.dumps(msg) or 'Market Research' in json.dumps(msg):
            print("SLACK MSG:", msg.get('text'))
            print("THREAD:", msg.get('replies'))

