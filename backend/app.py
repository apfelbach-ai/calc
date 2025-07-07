import json
import os
import time
import datetime
import decimal

# In-Memory "Datenbank" für die gespeicherten Aufgaben
# In einer echten Anwendung würde man hier eine Datenbank wie DynamoDB verwenden.
# problem_store = {} # Nicht mehr nötig, da DynamoDB verwendet wird

import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
# Stelle sicher, dass der Tabellenname korrekt ist
# Diesen Wert solltest du als Umgebungsvariable in Lambda festlegen, z.B. MATH_PROBLEMS_TABLE
# Für den Moment nehmen wir an, er ist direkt im Code.
# WICHTIG: Ersetze 'your-math-problems-table-name' durch den tatsächlichen Namen deiner DynamoDB-Tabelle!
table_name = os.environ.get('MATH_PROBLEMS_TABLE', 'KopfrechnenAufgaben') # Standardwert, wenn Env-Var nicht gesetzt
table = dynamodb.Table(table_name)

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super(DecimalEncoder, self).default(obj)

def generate_math_problem():
    num1 = random.randint(10, 99)
    num2 = random.randint(10, 99)
    operations = ['+', '-', '*']
    operation = random.choice(operations)
    
    problem_text = f"{num1} {operation} {num2}"
    correct_answer = eval(problem_text) # ACHTUNG: eval() ist riskant, hier aber ok für einfache Mathe

    # Eine eindeutige ID basierend auf der aktuellen Zeit
    problem_id = str(int(time.time()))

    # Speichere die Aufgabe und Antwort in DynamoDB
    # TTL (Time to Live) Attribut für 5 Minuten
    ttl_timestamp = int(time.time()) + 5 * 60 # Ablauf in 5 Minuten

    table.put_item(
        Item={
            'problem_id': problem_id,
            'correct_answer': correct_answer,
            'ttl': ttl_timestamp
        }
    )

    return {
        'problem': problem_text,
        'problem_id': problem_id
    }

def check_math_answer(problem_id, user_answer):
    response = table.get_item(
        Key={
            'problem_id': problem_id
        }
    )
    item = response.get('Item')

    if item is None:
        # Problem nicht gefunden oder abgelaufen
        return {
            'is_correct': False,
            'message': 'Problem nicht gefunden oder abgelaufen.'
        }
    
    correct_answer = item['correct_answer']
    
    # DynamoDB gibt Zahlen als Decimal zurück, konvertiere sie für den Vergleich
    db_correct_answer = int(correct_answer) if isinstance(correct_answer, decimal.Decimal) and correct_answer % 1 == 0 else float(correct_answer)
    
    if db_correct_answer == user_answer:
        return {
            'is_correct': True,
            'correct_answer': db_correct_answer # Auch hier den korrekten Wert zurückgeben
        }
    else:
        return {
            'is_correct': False,
            'correct_answer': db_correct_answer # Richtige Antwort immer zurückgeben
        }

import random # Sicherstellen, dass random importiert ist

def lambda_handler(event, context):
    print(f"DEBUG: Empfangenes Event: {json.dumps(event)}") # Das ganze Event im Log

    path = event.get('path', '/')
    print(f"DEBUG: Ursprünglicher Pfad: {path}")

    # API Gateway fügt oft den Stage-Namen zum Pfad hinzu (z.B. /prod/problem)
    # Entferne ihn, damit unser Routing funktioniert
    if path.startswith('/prod/'): # Wenn deine Stage 'prod' heißt
        path = path[len('/prod'):] # Entfernt '/prod' vom Pfad
    
    print(f"DEBUG: Bereinigter Pfad: {path}")

    http_method = event.get('httpMethod')

    if http_method == 'GET' and path == '/problem':
        problem_data = generate_math_problem()
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*', # Wichtig für CORS
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
            },
            'body': json.dumps(problem_data)
        }
    elif http_method == 'POST' and path == '/check':
        try:
            # Versuche, den Body zu parsen. Fange Fehler ab, wenn er leer oder ungültig ist.
            body_str = event.get('body')
            if body_str:
                body = json.loads(body_str)
                print(f"DEBUG: Parsed Body: {body}")
            else:
                print("DEBUG: Request body is empty.")
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Headers': 'Content-Type',
                        'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
                    },
                    'body': json.dumps({"error": "Request body is empty."})
                }

        except json.JSONDecodeError as e:
            print(f"ERROR: JSON parsing failed: {e}")
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
                },
                'body': json.dumps({"error": f"Invalid JSON in request body: {e}"})
            }
        except Exception as e:
            print(f"ERROR: Unexpected error when processing body: {e}")
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
                },
                'body': json.dumps({"error": f"Internal server error processing request body: {e}"})
            }

        problem_id = body.get('problem_id')
        user_answer = body.get('answer')

        if problem_id is None or user_answer is None:
            print("DEBUG: Missing problem_id or answer in request body.")
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
                },
                'body': json.dumps({"error": "Missing problem_id or answer."})
            }
        
        result = check_math_answer(problem_id, user_answer)
        print(f"DEBUG: check_math_answer result: {result}") # Debug-Ausgabe des Ergebnisses
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
            },
            'body': json.dumps(result, cls=DecimalEncoder)
        }
    else:
        # Fallback für unbekannte Pfade oder Methoden
        print(f"DEBUG: Unknown path or method: {path} {http_method}")
        return {
            'statusCode': 404,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Allow-Methods': 'OPTIONS,POST,GET'
            },
            'body': json.dumps({"message": "Ressource nicht gefunden."})
        }