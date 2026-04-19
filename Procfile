web: uvicorn web.app:app --host 0.0.0.0 --port $PORT
worker: functions-framework --target=generate_weekly_report --port=$PORT
