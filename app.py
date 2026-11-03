import os
import re
import uuid
from functools import wraps
from pathlib import Path

from flask import (
    Flask, render_template, request, redirect, session,
    url_for, flash, abort
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint, CheckConstraint
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "mude-esta-chave-antes-de-publicar"
)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///arttube.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024
app.config["UPLOAD_FOLDER"] = os.path.join(
    app.static_folder, "uploads"
)

Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
db = SQLAlchemy(app)

CATEGORIAS = [
    "Desenho", "Pintura", "Fotografia", "Atuação", "Filme",
    "Animação", "Música", "Dança", "Escultura", "Poesia",
    "Artesanato", "Outras artes"
]
IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
VIDEO_EXTENSIONS = {"mp4", "webm", "mov"}
ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

# Tabela de associação entre publicações e hashtags.
post_hashtags = db.Table(
    "post_hashtags",
    db.Column("post_id", db.Integer, db.ForeignKey("post.id"), primary_key=True),
    db.Column("hashtag_id", db.Integer, db.ForeignKey("hashtag.id"), primary_key=True)
)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)
    bio = db.Column(db.String(300), default="")

    posts = db.relationship(
        "Post", back_populates="artist", cascade="all, delete-orphan"
    )


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, default="")
    category = db.Column(db.String(50), nullable=False)
    media_filename = db.Column(db.String(255), nullable=False)
    media_type = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    artist = db.relationship("User", back_populates="posts")

    likes = db.relationship("Like", back_populates="post", cascade="all, delete-orphan")
    comments = db.relationship(
        "Comment", back_populates="post", cascade="all, delete-orphan",
        order_by="Comment.created_at.asc()"
    )
    hashtags = db.relationship(
        "Hashtag", secondary=post_hashtags, back_populates="posts"
    )


class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    post = db.relationship("Post", back_populates="likes")
    __table_args__ = (
        UniqueConstraint("user_id", "post_id", name="unique_user_post_like"),
    )


class Hashtag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    posts = db.relationship(
        "Post", secondary=post_hashtags, back_populates="hashtags"
    )


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(2000), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    author = db.relationship("User")
    post = db.relationship("Post", back_populates="comments")


class Follow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    followed_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    __table_args__ = (
        UniqueConstraint("follower_id", "followed_id", name="unique_follow"),
        CheckConstraint("follower_id != followed_id", name="no_self_follow"),
    )


class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    post = db.relationship("Post")
    __table_args__ = (
        UniqueConstraint("user_id", "post_id", name="unique_favorite"),
    )


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    text = db.Column(db.String(5000), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    sender = db.relationship("User", foreign_keys=[sender_id])
    receiver = db.relationship("User", foreign_keys=[receiver_id])


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Faça login para continuar.")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def current_user():
    user_id = session.get("user_id")
    return db.session.get(User, user_id) if user_id else None


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def liked_post_ids(user_id, posts):
    post_ids = [p.id for p in posts]
    if not post_ids:
        return set()
    rows = Like.query.filter(
        Like.user_id == user_id, Like.post_id.in_(post_ids)
    ).all()
    return {row.post_id for row in rows}


@app.route("/", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("feed"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(user_email=email).first()

        if user and check_password_hash(user.password, password):
            session.clear()
            session["user_id"] = user.id
            return redirect(url_for("feed"))

        flash("E-mail ou senha incorretos.")

    return render_template("login.html")


@app.route("/reg", methods=["GET", "POST"])
def reg():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        username = request.form.get("username", "").strip().lstrip("@")
        password = request.form.get("password", "")

        if not email or not username or not password:
            flash("Preencha todos os campos.")
        elif len(username) < 3 or len(username) > 50:
            flash("O nome de usuário deve ter entre 3 e 50 caracteres.")
        elif len(password) < 8:
            flash("A senha precisa ter pelo menos 8 caracteres.")
        elif User.query.filter_by(user_email=email).first():
            flash("Este e-mail já está cadastrado.")
        elif User.query.filter_by(username=username).first():
            flash("Este nome de usuário já está em uso.")
        else:
            user = User(
                user_email=email,
                username=username,
                password=generate_password_hash(password)
            )
            db.session.add(user)
            db.session.commit()
            flash("Conta criada! Agora faça login.")
            return redirect(url_for("login"))

    return render_template("registration.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@app.route("/feed")
@login_required
def feed():
    posts = Post.query.order_by(Post.created_at.desc(), Post.id.desc()).all()
    return render_template(
        "index.html",
        posts=posts,
        liked_ids=liked_post_ids(session["user_id"], posts),
        user=current_user()
    )


@app.route("/create")
@login_required
def create():
    return render_template("create_post.html", categorias=CATEGORIAS)


@app.route("/publish", methods=["POST"])
@login_required
def publish():
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    category = request.form.get("category", "")
    file = request.files.get("media")

    if not title or len(title) > 100:
        flash("Informe um título de até 100 caracteres.")
        return redirect(url_for("create"))
    if category not in CATEGORIAS:
        flash("Escolha uma categoria válida.")
        return redirect(url_for("create"))
    if not file or not file.filename or not allowed_file(file.filename):
        flash("Envie uma imagem ou vídeo em formato permitido.")
        return redirect(url_for("create"))

    original_name = secure_filename(file.filename)
    extension = original_name.rsplit(".", 1)[1].lower()
    unique_filename = f"{uuid.uuid4().hex}.{extension}"
    destination = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)
    file.save(destination)

    post = Post(
        title=title,
        description=description,
        category=category,
        media_filename=unique_filename,
        media_type="video" if extension in VIDEO_EXTENSIONS else "image",
        user_id=session["user_id"]
    )

    tag_names = set(re.findall(r"(?<!\w)#([a-zA-Z0-9_]{1,50})", description))
    for name in tag_names:
        normalized = name.lower()
        tag = Hashtag.query.filter_by(name=normalized).first()
        if tag is None:
            tag = Hashtag(name=normalized)
            db.session.add(tag)
        post.hashtags.append(tag)

    db.session.add(post)
    db.session.commit()
    flash("Sua arte foi publicada!")
    return redirect(url_for("feed"))


@app.route("/post/<int:post_id>")
@login_required
def post_detail(post_id):
    post = db.get_or_404(Post, post_id)
    liked = Like.query.filter_by(
        user_id=session["user_id"], post_id=post.id
    ).first() is not None
    saved = Favorite.query.filter_by(
        user_id=session["user_id"], post_id=post.id
    ).first() is not None
    return render_template("post.html", post=post, liked=liked, saved=saved)


@app.route("/like/<int:post_id>", methods=["POST"])
@login_required
def like(post_id):
    post = db.get_or_404(Post, post_id)
    existing = Like.query.filter_by(
        user_id=session["user_id"], post_id=post.id
    ).first()
    if existing:
        db.session.delete(existing)
    else:
        db.session.add(Like(user_id=session["user_id"], post_id=post.id))
    db.session.commit()
    return redirect(request.referrer or url_for("post_detail", post_id=post.id))


@app.route("/comment/<int:post_id>", methods=["POST"])
@login_required
def comment(post_id):
    post = db.get_or_404(Post, post_id)
    text = request.form.get("text", "").strip()
    if not text or len(text) > 2000:
        flash("O comentário deve ter entre 1 e 2000 caracteres.")
    else:
        db.session.add(Comment(
            text=text, user_id=session["user_id"], post_id=post.id
        ))
        db.session.commit()
    return redirect(url_for("post_detail", post_id=post.id))


@app.route("/follow/<int:user_id>", methods=["POST"])
@login_required
def follow(user_id):
    artist = db.get_or_404(User, user_id)
    current_id = session["user_id"]
    if current_id == artist.id:
        flash("Você não pode seguir a si mesmo.")
        return redirect(url_for("profile", user_id=user_id))

    existing = Follow.query.filter_by(
        follower_id=current_id, followed_id=artist.id
    ).first()
    if existing:
        db.session.delete(existing)
    else:
        db.session.add(Follow(follower_id=current_id, followed_id=artist.id))
    db.session.commit()
    return redirect(url_for("profile", user_id=user_id))


@app.route("/favorite/<int:post_id>", methods=["POST"])
@login_required
def favorite(post_id):
    post = db.get_or_404(Post, post_id)
    existing = Favorite.query.filter_by(
        user_id=session["user_id"], post_id=post.id
    ).first()
    if existing:
        db.session.delete(existing)
    else:
        db.session.add(Favorite(user_id=session["user_id"], post_id=post.id))
    db.session.commit()
    return redirect(request.referrer or url_for("post_detail", post_id=post.id))


@app.route("/favorites")
@login_required
def favorites():
    saved = Favorite.query.filter_by(
        user_id=session["user_id"]
    ).order_by(Favorite.id.desc()).all()
    return render_template("favorites.html", saved=saved)


@app.route("/profile/<int:user_id>")
@login_required
def profile(user_id):
    artist = db.get_or_404(User, user_id)
    posts = Post.query.filter_by(user_id=artist.id).order_by(
        Post.created_at.desc(), Post.id.desc()
    ).all()
    follower_count = Follow.query.filter_by(followed_id=artist.id).count()
    following_count = Follow.query.filter_by(follower_id=artist.id).count()
    is_following = Follow.query.filter_by(
        follower_id=session["user_id"], followed_id=artist.id
    ).first() is not None
    return render_template(
        "profile.html", artist=artist, posts=posts,
        follower_count=follower_count, following_count=following_count,
        is_following=is_following,
        liked_ids=liked_post_ids(session["user_id"], posts)
    )


@app.route("/explore")
@login_required
def explore():
    category = request.args.get("category", "").strip()
    tag_name = request.args.get("tag", "").strip().lstrip("#").lower()

    query = Post.query
    if category in CATEGORIAS:
        query = query.filter_by(category=category)
    if tag_name:
        tag = Hashtag.query.filter_by(name=tag_name).first()
        query = query.filter(Post.id.in_(
            [p.id for p in tag.posts]
        )) if tag else query.filter(Post.id == -1)

    posts = query.order_by(Post.created_at.desc(), Post.id.desc()).all()
    return render_template(
        "explore.html", posts=posts, categorias=CATEGORIAS,
        categoria_atual=category, tag_atual=tag_name,
        liked_ids=liked_post_ids(session["user_id"], posts)
    )


@app.route("/hashtag/<string:name>")
@login_required
def hashtag(name):
    tag = Hashtag.query.filter_by(name=name.lower().lstrip("#")).first_or_404()
    posts = Post.query.filter(Post.hashtags.any(Hashtag.id == tag.id)).order_by(
        Post.created_at.desc()
    ).all()
    return render_template(
        "explore.html", posts=posts, categorias=CATEGORIAS,
        categoria_atual="", tag_atual=tag.name,
        liked_ids=liked_post_ids(session["user_id"], posts)
    )


@app.route("/messages")
@login_required
def messages():
    current_id = session["user_id"]
    sent_ids = db.session.query(Message.receiver_id).filter_by(sender_id=current_id)
    received_ids = db.session.query(Message.sender_id).filter_by(receiver_id=current_id)
    contact_ids = {row[0] for row in sent_ids.union(received_ids).all()}
    contacts = User.query.filter(User.id.in_(contact_ids)).order_by(User.username).all() if contact_ids else []
    return render_template("messages.html", contacts=contacts)


@app.route("/messages/<int:user_id>")
@login_required
def conversation(user_id):
    current_id = session["user_id"]
    if current_id == user_id:
        return redirect(url_for("messages"))
    other_user = db.get_or_404(User, user_id)
    conversation_messages = Message.query.filter(
        db.or_(
            db.and_(Message.sender_id == current_id, Message.receiver_id == user_id),
            db.and_(Message.sender_id == user_id, Message.receiver_id == current_id)
        )
    ).order_by(Message.created_at.asc(), Message.id.asc()).all()
    return render_template(
        "conversation.html", other_user=other_user,
        messages=conversation_messages
    )


@app.route("/messages/send/<int:user_id>", methods=["POST"])
@login_required
def send_message(user_id):
    current_id = session["user_id"]
    if current_id == user_id:
        return redirect(url_for("messages"))
    db.get_or_404(User, user_id)
    text = request.form.get("text", "").strip()
    if not text or len(text) > 5000:
        flash("A mensagem deve ter entre 1 e 5000 caracteres.")
        return redirect(url_for("conversation", user_id=user_id))
    db.session.add(Message(
        sender_id=current_id, receiver_id=user_id, text=text
    ))
    db.session.commit()
    return redirect(url_for("conversation", user_id=user_id))


@app.context_processor
def inject_current_user():
    return {"current_user": current_user()}


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)