import json


class QuotEncoder(json.JSONDecoder):
    def decode(self, s, _w=None):
        s = s.replace('&quot;', '\"')
        return json.JSONDecoder.decode(self, s)
