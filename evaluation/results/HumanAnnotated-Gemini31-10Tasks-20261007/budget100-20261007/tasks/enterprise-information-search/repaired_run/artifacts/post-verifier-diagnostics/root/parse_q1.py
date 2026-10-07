import json

with open('/root/DATA/products/CoachForce.json', 'r') as f:
    data = json.load(f)

for doc in data.get('docs', []):
    print("DOC ID:", doc.get('doc_id'))
    print("TITLE:", doc.get('title'))
    print("TYPE:", doc.get('document_type'))
    print("AUTHOR:", doc.get('author'))
    print("REVIEWERS:", doc.get('reviewers'))
    print("KEY REVIEWERS:", doc.get('key_reviewers'))
    print("---")

for meeting in data.get('meetings', []):
    print("MEETING:", meeting.get('meeting_id'))
    print("TOPIC:", meeting.get('topic'))
    print("PARTICIPANTS:", meeting.get('participants'))
    print("---")
