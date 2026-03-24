# src/plugins/chatbot/cards.py

def count_card(title: str, subtitle: str, count: int):
    body = [{"type": "TextBlock", "text": title, "weight": "Bolder", "size": "Medium"}]
    if subtitle:
        body.append({"type": "TextBlock", "text": subtitle, "isSubtle": True, "spacing": "None"})
    body.append({"type": "TextBlock", "text": f"**{count}**", "size": "ExtraLarge", "weight": "Bolder"})
    return {"type": "AdaptiveCard","body": body,"$schema":"http://adaptivecards.io/schemas/adaptive-card.json","version":"1.4"}

def list_card(title: str, rows, fields):
    body = [{"type":"TextBlock","text":title,"weight":"Bolder","size":"Medium"}]
    for r in rows:
        text = " • " + " | ".join(f"{k}: {r.get(k,'')}" for k in fields)
        body.append({"type":"TextBlock","text":text,"wrap":True})
    return {"type":"AdaptiveCard","body":body,"$schema":"http://adaptivecards.io/schemas/adaptive-card.json","version":"1.4"}

def kv_card(title: str, kv: dict):
    body = [{"type":"TextBlock","text":title,"weight":"Bolder","size":"Medium"}]
    for k,v in kv.items():
        body.append({"type":"TextBlock","text":f"**{k}:** {v}","wrap":True})
    return {"type":"AdaptiveCard","body":body,"$schema":"http://adaptivecards.io/schemas/adaptive-card.json","version":"1.4"}