from flask import Flask, render_template, request, session, redirect, url_for,make_response
from flask_socketio import join_room, leave_room, send, SocketIO
import random
from string import ascii_uppercase
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO

import spotipy
from spotipy.oauth2 import SpotifyOAuth


app = Flask(__name__)
app.config["SECRET_KEY"] = "hjhjsdahhds"
socketio = SocketIO(app)

rooms = {}

def generate_unique_code(length):
    while True:
        code = ""
        for _ in range(length):
            code += random.choice(ascii_uppercase)
        
        if code not in rooms:
            break
    
    return code

@app.route("/", methods=["POST", "GET"])
def home():
    session.clear()
    if request.method == "POST":
        name = request.form.get("name")
        code = request.form.get("code")
        join = request.form.get("join", False)
        create = request.form.get("create", False)

        if not name:
            return render_template("home.html", error="Please enter a name.", code=code, name=name)

        if join != False and not code:
            return render_template("home.html", error="Please enter a room code.", code=code, name=name)
        
        room = code
        if create != False:
            room = generate_unique_code(4)
            rooms[room] = {"members": 0, "messages": []}
        elif code not in rooms:
            return render_template("home.html", error="Room does not exist.", code=code, name=name)
        
        session["room"] = room
        session["name"] = name
        return redirect(url_for("room"))

    return render_template("home.html")

@app.route("/room")
def room():
    room = session.get("room")
    if room is None or session.get("name") is None or room not in rooms:
        return redirect(url_for("home"))

    return render_template("room.html", code=room, messages=rooms[room]["messages"])

@socketio.on("message")
def message(data):
    room = session.get("room")
    if room not in rooms:
        return 
    
    content = {
        "name": session.get("name"),
        "message": data["data"]
    }
    send(content, to=room)
    rooms[room]["messages"].append(content)
    print(f"{session.get('name')} said: {data['data']}")

@socketio.on("connect")
def connect(auth):
    room = session.get("room")
    name = session.get("name")
    if not room or not name:
        return
    if room not in rooms:
        leave_room(room)
        return
    
    join_room(room)
    send({"name": name, "message": "has entered the room"}, to=room)
    rooms[room]["members"] += 1
    print(f"{name} joined room {room}")

@socketio.on("disconnect")
def disconnect():
    room = session.get("room")
    name = session.get("name")
    leave_room(room)

    if room in rooms:
        rooms[room]["members"] -= 1
        if rooms[room]["members"] <= 0:
            del rooms[room]
    
    send({"name": name, "message": "has left the room"}, to=room)
    print(f"{name} has left the room {room}")


@app.route("/generate_pdf")
def generate_pdf():
    room = session.get("room")
    if room is None or session.get("name") is None or room not in rooms:
        return redirect(url_for("home"))

    # Create a PDF and add chat history to it
    chat_history = rooms[room]["messages"]
    
    # Create a BytesIO buffer to store the PDF data
    pdf_buffer = BytesIO()

    # Create a PDF object
    c = canvas.Canvas(pdf_buffer, pagesize=letter)
    c.setFont("Helvetica", 12)

    # Initialize y-coordinate for positioning messages
    y = c._pagesize[1] - 100

    for message in chat_history:
        name = message["name"]
        message_text = message["message"]
        message_line = f"{name}: {message_text}"
        
        # Check if adding this message would exceed the page height
        if y < 50:
            c.showPage()  # Start a new page
            y = c._pagesize[1] - 100  # Reset y-coordinate

        c.drawString(50, y, message_line)
        y -= 20  # Adjust the y-coordinate for the next message

    c.save()

    # Set the response content type to PDF
    response = make_response(pdf_buffer.getvalue())
    response.headers["Content-Type"] = "application/pdf"

    # Set the file name for the downloaded PDF
    response.headers["Content-Disposition"] = "inline; filename=chat_history.pdf"

    return response


def song(song_name):
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id="39e7f094c3b8498c86877a99013f3434",
    client_secret="babe73cd284d4d9ca6b70f7aeb2495d3",
    redirect_uri="http://localhost:8000/auth/callback",
    scope="user-library-read"
    ))

    #song_name = "anbe en anbe"
    results = sp.search(q=song_name, type="track")

    track = results['tracks']['items'][0]
    track_name = track['name']
    artist_name = track['artists'][0]['name']
    track_uri = track['uri']


    track_details = sp.track(track_uri)
    # Access additional details like album name, release date, etc.

    id  = track_details['external_urls']['spotify']
    print(id)
    track_id = id.split('/track/')[1]
        
    # Create the embedded URL
    embedded_url = f'https://open.spotify.com/embed/track/{track_id}'
    return embedded_url

@socketio.on("song_request")
def handle_song_request(data):
    song_name = data["song_name"]
    # Call your song function to get the Spotify URL
    spotify_url = song(song_name)
    print(spotify_url)
    socketio.emit("song_url", {"url": spotify_url})


if __name__ == "__main__":
    socketio.run(app, debug=True)