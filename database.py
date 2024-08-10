import sqlite3
import logging


class Database:
    def __init__(self, db_file):
        self.db_file = db_file
        self.logger = logging.getLogger('Database')
        self.logger.setLevel(logging.ERROR)
        fh = logging.FileHandler('log_file.txt')
        self.logger.addHandler(fh)
        self.logger.info('Database initialization started...')

        self.init_db()  # Создание таблицы при инициализации

        try:
            with sqlite3.connect(self.db_file) as conn:
                self.logger.info(f"Connected to database {self.db_file}")
        except sqlite3.OperationalError:
            self.logger.error(f"Database {self.db_file} not found")
            print(f"Database {self.db_file} not found")

    def execute_query(self, query, params=None):
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            conn.commit()

    def fetch_one(self, query, params=None):
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            row = cursor.fetchone()
            if row:
                columns = [d[0] for d in cursor.description]
                return dict(zip(columns, row))
            else:
                return None

    def init_db(self):
        try:
            self.execute_query(
                '''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, prompt TEXT, answer TEXT, session_count INTEGER DEFAULT 0, session_tokens INTEGER DEFAULT 0)''')
            #self.execute_query('''ALTER TABLE users ADD COLUMN prompt TEXT''')
            self.logger.info("Database initialization successful.")
        except Exception as e:
            self.logger.error(f"Error initializing database: {str(e)}")

    def create_user_if_not_exist(self, user_id):
        self.execute_query('''INSERT OR IGNORE INTO users (user_id, prompt, answer, session_count, session_tokens)
                             VALUES (?, '', '', 0, 0)''', (user_id,))

    def save_prompt_to_db(self, user_id, prompt):
        self.execute_query('''UPDATE users SET prompt = ? WHERE user_id = ?''', (prompt, user_id))

    def update_prompt(self, user_id, prompt):
        self.execute_query('''UPDATE users SET prompt = ? WHERE user_id = ?''', (prompt, user_id))

    def update_answer(self, user_id, answer):
        self.execute_query('''UPDATE users SET answer = ? WHERE user_id = ?''', (answer, user_id))

    def update_session_count(self, user_id, new_count):
        connection = sqlite3.connect(self.db_file)
        cursor = connection.cursor()
        cursor.execute('UPDATE users SET session_count = ? WHERE user_id = ?', (new_count, user_id))
        connection.commit()
        connection.close()

    def update_session_tokens(self, user_id, new_tokens):
        session_count, session_tokens = self.get_session_data(user_id)
        self.execute_query('UPDATE users SET session_tokens = ? WHERE user_id = ?',
                           (new_tokens + session_tokens, user_id))

    def get_session_data(self, user_id):
        connection = sqlite3.connect(self.db_file)
        cursor = connection.cursor()
        cursor.execute('SELECT session_count, session_tokens FROM users WHERE user_id = ?', (user_id,))
        session_data = cursor.fetchone()
        connection.close()
        return session_data if session_data else (0, 0)
