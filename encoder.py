import json


class QuotEncoder(json.JSONDecoder):
    def decode(self, s):
        s = s.replace('&quot;', '\"')
        return json.JSONDecoder.decode(self, s)
