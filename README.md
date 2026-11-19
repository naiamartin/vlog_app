# Run VlogApp

From the project root set up and start the backend:

   ```sh
   python -m venv .venv
   . .venv/bin/activate
   pip install -r requirements.txt
   uvicorn backend.main:app --reload
   ```

3. Open [http://localhost:8000/register](http://localhost:8000/register).
