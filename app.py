#flask frameworkü, request kullanıcıdan gelen http isteklerini okuyacak
#jsonify pthon sözlüğünü (dict) json formatına dönüştürüp API cevabı olarak döndürcek
from flask import Flask, request, jsonify
import pandas as pd
from flask import Flask, request, jsonify
import pandas as pd
from flask_cors import CORS

app = Flask(__name__)
CORS(app)




df = pd.read_csv("emotion_map.csv",sep =';')

#ana route kontrol amaçlı:
@app.route("/")

#burada tarayıcadaki kök adrese /  gidilince bu fonksiyon çalışasacak
def home():
    return "Tangible Emphaty Backend is working properly"


@app.route("/analyze", methods=["POST"])

def analyze():
    data = request.get_json() #data kullanıcıdan gelen JSON tipindekiveriyi okuyacak
    
    #gönderilen JSON daki text anahtarını alırızı yoksa empty döner
    #bir de tolwer yapıyoruz
    text = data.get("text","").lower() 
    
    #her satırı ontorl ediyorum burada:
    for _, row in df.iterrows():
        #her duygununn keywordüne bakacağım ; ile ayırıp
        for kw in row["keywords"].split(";"):
            if kw.strip().lower() in text:
                
                return jsonify(
                    {
                        "emotion": row["emotion_label"],
                        "valence" : float(row["valence"]),
                        "arousal" : float(row["arousal"]),
                        "shape_params":{
                            "curvature": float(row["curvature"]),
                            "sharpness": float(row["sharpness"]),
                            "symmetry": float(row["symmetry"]),
                            "twist": float(row["twist"]),  
                            "noise": float(row["noise"]),
                            "hole_count": int(row["hole_count"])  
                            
                        }                 
                                                
                    })

    return jsonify({"error : no matching emotion found"}), 404    


if __name__ == "__main__":
    
    app.run(debug=True)


