import json

def get_q1():
    with open('/root/DATA/products/CoachForce.json', 'r') as f:
        data = json.load(f)
        
    print("\nMeeting transcripts:")
    for m in data.get('meeting_transcripts', []):
        if 'market research' in m.get('document_type', '').lower():
            print(f"Meeting ID: {m.get('id')} - Type: {m.get('document_type')}")
            transcript = m.get('transcript', '')
            lines = transcript.split('\n')
            for line in lines:
                text = line.lower()
                if 'feedback' in text or 'suggest' in text or 'add' in text or 'think' in text or 'should' in text:
                    print(f"  {line[:150]}")
            
    print("\nAlso check slack:")
    for s in data.get('slack', []):
        text = s.get('Message', '')
        if isinstance(text, dict):
            text = json.dumps(text)
        if 'latest_cofoaix_market_research_report' in text or 'final_cofoaix_market_research_report' in text or 'cofoaix_market_research_report' in text:
            print(f"Thread ID: {s.get('id')}")
            if 'ThreadReplies' in s:
                for reply in s['ThreadReplies']:
                    print(f"  Reply from {reply.get('sender')}: {str(reply)[:100]}")

get_q1()
