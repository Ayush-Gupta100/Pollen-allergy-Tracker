from flask import Flask, render_template, request, redirect, session
from flask_mail import Mail, Message
import sqlite3, random
import requests
import sklearn
import pickle
import numpy as np
from twilio.rest import Client

app = Flask(__name__)
app.secret_key = "secret"

# Mail Config
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'ayushg2500@gmail.com'
app.config['MAIL_PASSWORD'] = 'mpba lkpz cqtv spsj'

mail = Mail(app)

# DB Setup
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    email TEXT PRIMARY KEY,
                    phone TEXT,
                    password TEXT,
                    allergic INTEGER DEFAULT 0
                )''')
    conn.commit()
    conn.close()

@app.route('/')
def front():
    return render_template('front.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        session['email'] = request.form['email']
        session['phone'] = request.form['phone']
        session['password'] = request.form['password']
        session['otp'] = str(random.randint(100000, 999999))

        msg = Message("Your OTP for Allergy Tracker", sender="ayushg2500@gmail.com", recipients=[session['email']])
        msg.body = f"Your OTP is {session['otp']}"
        mail.send(msg)
        return redirect('/verify')
    return render_template('register.html')

@app.route('/verify', methods=['GET', 'POST'])
def verify():
    if request.method == 'POST':
        entered_otp = request.form['otp']
        if entered_otp == session['otp']:
            conn = sqlite3.connect('users.db')
            c = conn.cursor()

            # ✅ Check if email already exists
            c.execute("SELECT * FROM users WHERE email = ?", (session['email'],))
            existing_user = c.fetchone()

            if existing_user:
                conn.close()
                return "❗ This email is already registered. Please log in."

            # ✅ Insert new user
            c.execute("INSERT INTO users VALUES (?, ?, ?,?)", (session['email'], session['phone'], session['password'],0))
            conn.commit()
            conn.close()

            session['logged_in'] = True
            return redirect('/login')
        else:
            return "❌ Incorrect OTP!"
    return render_template('verify.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
        user = c.fetchone()
        conn.close()

        if user:
            session['email'] = email
            return redirect('/dashboard')
        else:
            return "Invalid email or password"

    return render_template('login.html')

@app.route('/save_location', methods=['POST'])
def save_location():
    data = request.get_json()
    session['lat'] = data.get('latitude')
    session['lon'] = data.get('longitude')
    # print(f"Saved to session: lat={session['lat']}, lon={session['lon']}")
    return f"Received location: ({session['lat']}, {session['lon']})"


@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'email' not in session:
        return redirect('/login')

    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    if request.method == 'POST':
        allergic = int(request.form['allergic'])
        c.execute("UPDATE users SET allergic = ? WHERE email = ?", (allergic, session['email']))
        conn.commit()

    # Get current allergy status
    c.execute("SELECT allergic FROM users WHERE email = ?", (session['email'],))
    result = c.fetchone()
    allergic = result[0] if result else 0
    # Simulate allergy zone status (can be replaced with real API)
    in_allergic_area =False
    conn.close()

    print(session['email'])
    print(allergic,"\n",in_allergic_area)
    lat = session.get('lat', 70)
    lon = session.get('lon', 80)
    print("User location from session:", lat, lon)



    headers = {
    "x-api-key": "312a856f52fc6802d3d03b1115dead5df78f538a28e9d987158fe16d93bcce0b"  # ✅ Replace with real key
        }

    params = {
    "lat": lat,
    "lng": lon
    }

    url = "https://api.ambeedata.com/latest/pollen/by-lat-lng"
    pollen_grass=0
    pollen_weed=0
    pollen_tree=0
    res = requests.get(url, headers=headers, params=params)
    if res.status_code == 200:
        data = res.json()
        if data['data']==[]:
            print("❌ Failed")
        else:
            d=data['data'][0]
            print("🌿 Pollen Data:", d['Count'])
            pollen_grass=d['Count']['grass_pollen']
            pollen_weed=d['Count']['weed_pollen']
            pollen_tree=d['Count']['tree_pollen']
    else:
        print(f"❌ Failed: {res.status_code} — {res.text}")

    with open('model.pkl', 'rb') as file:
        loaded_model = pickle.load(file)

    # API for Temp
    url3=f"http://api.airvisual.com/v2/nearest_city?lat={lat}&lon={lon}&key=6f9738f4-3820-4c1f-92a0-89bf3b89ae53"
    res3=requests.get(url3)
    data3=res3.json()
    print(data3)
    # Check for valid response
    if res3.status_code == 200 and 'data' in data3 and 'current' in data3['data']:
        weather = data3['data']['current']['weather']
        pollution = data3['data']['current']['pollution']

        humid = weather['hu']
        temp = weather['tp']
        wind_speed = weather['ws'] * 3.6
        pm_2_5 = pollution['aqius']
        pm_10 = pollution['aqicn']
        print("Sucessfully fetched weather data")
        print(lat,lon)
    else:
        print("❌ Error: Invalid weather API response:", data3)
        # Use default values or return an error
        humid = 50
        temp = 25
        wind_speed = 10
        pm_2_5 = 30
        pm_10 = 50
    print("pm 2.5 : "+str(pm_2_5)+"\npm 10 : "+str(pm_10))
    print("temp",temp)
    print("humid",humid)
    print("wind_speed",wind_speed)
    print(pollen_grass,pollen_tree,pollen_weed)
    ans=loaded_model.predict(np.array([temp,humid,pm_2_5,pm_10,wind_speed,pollen_grass,pollen_tree,pollen_weed]).reshape(1,-1))
    print(ans)
    if ans==1:
        in_allergic_area=False
    else:
        in_allergic_area=True
    if allergic==True and in_allergic_area==True:
        mail = Mail(app)

        with app.app_context():
            msg = Message(
                subject="Pollen Alert",
                sender="ayushg2500@gmail.com",
                recipients=[session['email']],
                body="Pollen level is high today. Stay indoors!"
            )
            mail.send(msg)
    return render_template('dashboard.html', email=session['email'],allergic=allergic, in_allergic_area=in_allergic_area)

@app.route('/ping')
def ping():
    return "Ping OK", 200

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
