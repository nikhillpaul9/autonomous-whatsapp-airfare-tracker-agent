@echo off
:: Navigate to your project folder
cd D:\AI Projects\Langraph_Projects\whatsapp_flight_tracker

:: Activate the virtual environment
call venv\Scripts\activate

:: Run the daily worker script
python daily_worker.py

:: (Optional) Deactivate when done
deactivate