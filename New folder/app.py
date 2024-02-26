from flask import Flask, request, flash, render_template_string, render_template, jsonify, redirect, url_for, session, Response
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, ForeignKey
from crewai import Agent, Task, Crew, Process
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import zipfile
import base64
from io import BytesIO
import os
from flask import session as flask_session

app = Flask(__name__)
app.secret_key = "nisai8is1234"

db_uri = 'mysql+mysqlconnector://root:@localhost/crew4'
engine = create_engine(db_uri)
Session = sessionmaker(bind=engine)

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    openai_api_key = Column(String(255), unique=True)

class CAgent(Base):
    __tablename__ = 'agents'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    role = Column(String(255), nullable=False)
    goal = Column(Text, nullable=False)
    verbose = Column(Boolean, nullable=False)
    backstory = Column(Text, nullable=False)
    allow_delegation = Column(Boolean, nullable=False)

class CTask(Base):
    __tablename__ = 'tasks'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    agent_id = Column(Integer, ForeignKey('agents.id'))
    task_name = Column(String(255), nullable=False)
    task_description = Column(Text, nullable=False)

class TaskResult(Base):
    __tablename__ = 'task_results'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    task_id = Column(Integer, ForeignKey('tasks.id'))
    result = Column(Text, nullable=False)

    # Define any additional columns or relationships as needed


Base.metadata.create_all(engine)

def create_session():
    return Session()

@app.route('/')
def index():
    agents = []
    tasks = []

    if 'user_id' in flask_session:
        user_id = flask_session['user_id']
        session = create_session()
        try:
            agents = session.query(CAgent).filter_by(user_id=user_id).all()
            tasks = session.query(CTask).filter_by(user_id=user_id).all()
        except Exception as e:
            flash(f"Error: {e}")
        finally:
            session.close()

    return render_template('api_key_form.html', agents=agents, tasks=tasks)



from flask import jsonify

@app.route('/get_agent_details/<int:agent_id>')
def get_agent_details(agent_id):
    # Logic to fetch agent details based on agent_id
    agent_details = {
        'role': 'Agent Role',
        'goal': 'Agent Goal',
        'verbose': True,
        'backstory': 'Agent Backstory',
        'allow_delegation': True
    }
    return jsonify(agent_details)



@app.route('/set_api_key', methods=['POST'])
def set_api_key():
    if request.method == 'POST':
        openai_api_key = request.form['openai_api_key']
        db_session = create_session()
        try:
            user = db_session.query(User).filter_by(openai_api_key=openai_api_key).first()
            if user:
                flask_session['user_id'] = user.id  # Storing user ID in session
                flask_session['openai_api_key'] = openai_api_key  # Store API key in session
                flash('Login success!', 'success')
            else:
                new_user = User(openai_api_key=openai_api_key)
                db_session.add(new_user)
                db_session.commit()
                flask_session['user_id'] = new_user.id  # Storing new user ID in session
                flask_session['openai_api_key'] = openai_api_key  # Store API key in session
                flash('API Key set successfully!', 'success')
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
        finally:
            db_session.close()
        return redirect(url_for('index'))
    # If the request method is GET, redirect to index
    return redirect(url_for('index'))

@app.route('/create_agent', methods=['POST'])
def create_agent():
    if 'user_id' in flask_session:
        user_id = flask_session['user_id']
        role = request.form['role']
        goal = request.form['goal']
        verbose = request.form['verbose'] == 'true'
        backstory = request.form['backstory']
        allow_delegation = request.form['allow_delegation'] == 'true'

        session = create_session()
        try:
            agent = CAgent(user_id=user_id, role=role, goal=goal, verbose=verbose, backstory=backstory, allow_delegation=allow_delegation)
            session.add(agent)
            session.commit()
            flash('CAgent created successfully!', 'success')
        except Exception as e:
            flash(f'Error creating agent: {str(e)}', 'error')
            session.rollback()
        finally:
            session.close()
    else:
        flash('You must be logged in to create an agent.', 'error')

    return redirect(url_for('index'))

@app.route('/create_task', methods=['POST'])
def create_task():
    if 'user_id' in flask_session:
        user_id = flask_session['user_id']
        agent_id = request.form['selected_agent']
        task_name = request.form['task_name']
        task_description = request.form['task_description']

        session = create_session()
        try:
            task = CTask(user_id=user_id, agent_id=agent_id, task_name=task_name, task_description=task_description)
            session.add(task)
            session.commit()
            flash('CTask added successfully!', 'success')
        except Exception as e:
            flash(f'Error adding task: {str(e)}', 'error')
            session.rollback()
        finally:
            session.close()
    else:
        flash('You must be logged in to create a task.', 'error')

    return redirect(url_for('index'))

@app.route('/delete_task', methods=['POST'])
def delete_task():
    if 'user_id' in flask_session:
        task_id = request.form['task_id']
        session = create_session()
        try:
            task = session.query(CTask).filter_by(id=task_id).first()
            if task:
                session.delete(task)
                session.commit()
                flash('CTask deleted successfully!', 'success')
            else:
                flash('CTask not found.', 'error')
        except Exception as e:
            flash(f'Error deleting task: {str(e)}', 'error')
            session.rollback()
        finally:
            session.close()
    else:
        flash('You must be logged in to delete a task.', 'error')

    return redirect(url_for('index'))

@app.route('/reassign_task', methods=['POST'])
def reassign_task():
    if 'user_id' in flask_session:
        task_id = request.form['task_id']
        new_agent_id = request.form['new_agent_id']

        session = create_session()
        try:
            task = session.query(CTask).filter_by(id=task_id).first()
            if task:
                # Create a new task with the same details but a different ID
                new_task = CTask(
                    user_id=task.user_id,
                    agent_id=new_agent_id,
                    task_name=task.task_name,
                    task_description=task.task_description
                )
                session.add(new_task)
                session.commit()

                flash('Task reassigned successfully!', 'success')
            else:
                flash('Task not found.', 'error')
        except Exception as e:
            flash(f'Error reassigning task: {str(e)}', 'error')
            session.rollback()
        finally:
            session.close()
    else:
        flash('You must be logged in to reassign a task.', 'error')

    return redirect(url_for('index'))


@app.route('/execute_tasks', methods=['POST'])
def execute_tasks():
    if 'user_id' not in flask_session or 'openai_api_key' not in flask_session:
        flash('You must be logged in and have an API key set to execute tasks.', 'error')
        return redirect(url_for('index'))

    selected_task_ids = request.json.get('selected_tasks')

    user_id = flask_session['user_id']
    os.environ['OPENAI_API_KEY'] = flask_session.get('openai_api_key')
    openai_api_key = os.environ['OPENAI_API_KEY']

    session = create_session()
    with session.begin():
        agents = []
        tasks = []
        for task_id in selected_task_ids:
            task_agent_data = session.query(CTask.task_description, CAgent.role, CAgent.goal, CAgent.verbose, CAgent.backstory, CAgent.allow_delegation).join(CAgent, CTask.agent_id == CAgent.id).filter(CTask.id == task_id, CTask.user_id == user_id).first()
            print(task_agent_data)

            if task_agent_data:
                agent = Agent(role=task_agent_data[1], goal=task_agent_data[2], verbose=task_agent_data[3], backstory=task_agent_data[4], allow_delegation=task_agent_data[5], openai_api_key=openai_api_key)
                task = Task(description=task_agent_data[1], agent=agent)
                agents.append(agent)
                tasks.append(task)


                if not tasks:
                    flash('No tasks selected or tasks not found.', 'error')
                    return redirect(url_for('index'))

            app_dev_crew = Crew(api_key=openai_api_key, agents=agents, tasks=tasks, process=Process.sequential)
            result = app_dev_crew.kickoff()

            in_memory_zip = BytesIO()
            with zipfile.ZipFile(in_memory_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zipf:
                results_str = f"Result:\n{result}"
                zipf.writestr('task_results.txt', results_str)
                complete_code = consolidate_code()
                zipf.writestr('consolidated_code.py', complete_code)

            in_memory_zip.seek(0)
            encoded_zip = base64.b64encode(in_memory_zip.read()).decode('utf-8')

            return jsonify({'result': result, 'encoded_zip': encoded_zip})

def consolidate_code():
    with open(__file__, 'r') as file:
        code_content = file.read()
    return code_content

if __name__ == '__main__':
    app.run(debug=True)
