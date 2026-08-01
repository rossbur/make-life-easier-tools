# app.py
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import jwt
import bcrypt
from apscheduler.schedulers.background import BackgroundScheduler
from flask_cors import CORS

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
db = SQLAlchemy(app)
CORS(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    
    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    
    def check_password(self, password):
        return bcrypt.checkpw(password.encode(), self.password_hash)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.DateTime)
    completed = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(200))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# API Routes
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    user = User(email=data['email'])
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()
    return jsonify({'message': 'User registered'})

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(email=data['email']).first()
    if user and user.check_password(data['password']):
        token = jwt.encode({
            'user_id': user.id,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }, app.config['SECRET_KEY'], algorithm='HS256')
        return jsonify({'token': token})
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/tasks', methods=['GET', 'POST'])
def tasks():
    if request.method == 'GET':
        tasks = Task.query.filter_by(user_id=request.args.get('user_id')).all()
        return jsonify([task.to_dict() for task in tasks])
    elif request.method == 'POST':
        task = Task(**request.get_json())
        db.session.add(task)
        db.session.commit()
        return jsonify({'message': 'Task created'})

# Scheduler Setup
scheduler = BackgroundScheduler()
scheduler.add_job(func=send_notifications, trigger="interval", minutes=5)
scheduler.start()

if __name__ == '__main__':
    app.run(debug=True)

// src/App.tsx
import React, { useState, useEffect } from 'react';
import axios from 'axios';

interface Task {
  id: number;
  title: string;
  description?: string;
  dueDate?: string;
  completed: boolean;
}

const App: React.FC = () => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [newTask, setNewTask] = useState<Omit<Task, 'id' | 'completed'>>({ 
    title: '', 
    description: '',
    dueDate: ''
  });

  useEffect(() => {
    fetchTasks();
  }, []);

  const fetchTasks = async () => {
    try {
      const response = await axios.get('/api/tasks');
      setTasks(response.data);
    } catch (error) {
      console.error('Error fetching tasks:', error);
    }
  };

  const addTask = async () => {
    try {
      const response = await axios.post('/api/tasks', newTask);
      setTasks([...tasks, response.data]);
      setNewTask({ title: '', description: '', dueDate: '' });
    } catch (error) {
      console.error('Error adding task:', error);
    }
  };

  return (
    <div className="app">
      <h1>Task Manager</h1>
      <div className="add-task">
        <input
          type="text"
          placeholder="Title"
          value={newTask.title}
          onChange={(e) => setNewTask({...newTask, title: e.target.value})}
        />
        <input
          type="date"
          value={newTask.dueDate || ''}
          onChange={(e) => setNewTask({...newTask, dueDate: e.target.value})}
        />
        <button onClick={addTask}>Add Task</button>
      </div>
      <ul>
        {tasks.map(task => (
          <li key={task.id}>
            <span>{task.title}</span>
            <span>{task.dueDate}</span>
          </li>
        ))}
      </ul>
    </div>
  );
};

export default App;

# notification_service.py
from flask_mail import Mail, Message
import pusher
import asyncio
import aiohttp

class NotificationService:
    def __init__(self, mail_config, pusher_config):
        self.mail = Mail()
        self.mail.init_app(mail_config)
        self.pusher_client = pusher.Pusher(
            app_id=pusher_config['app_id'],
            key=pusher_config['key'],
            secret=pusher_config['secret'],
            cluster=pusher_config['cluster']
        )
        
    async def send_task_reminder(self, user_id, task):
        # Send push notification
        self.pusher_client.trigger(
            f'user-{user_id}',
            'task-reminder',
            {'task': task.to_dict()}
        )
        
        # Send email reminder
        msg = Message(
            subject=f'Task Reminder: {task.title}',
            recipients=[user.email],
            body=f'Your task "{task.title}" is due soon'
        )
        self.mail.send(msg)
        
        # Check if browser supports Web Push
        if user.web_push_subscriptions:
            await self._send_web_push(user.web_push_subscriptions, task)
            
    async def _send_web_push(self, subscriptions, task):
        headers = {
            'Authorization': 'Bearer ' + WEB_PUSH_SERVER_KEY,
            'Content-Type': 'application/json'
        }
        
        payload = {
            'title': 'Task Reminder',
            'body': f'{task.title} is due soon',
            'icon': '/favicon.ico'
        }
        
        async with aiohttp.ClientSession() as session:
            for sub in subscriptions:
                await session.post(
                    sub.endpoint,
                    headers=headers,
                    json=payload
                )
