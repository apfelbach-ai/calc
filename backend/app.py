import random
import json
import os
import boto3 # Dies ist das AWS SDK für Python

# Initialisiere den DynamoDB-Client außerhalb der Funktion
# Dies verbessert die Leistung bei "warmen" Lambda-Starts
dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('DYNAMODB_TABLE_NAME', 'KopfrechnenAufgaben') # Holt den Tabellennamen aus Umgebungsvariablen
table = dynamodb.Table(table_name)

# KEIN temp_problem_store mehr!


def generate_math_problem():
    num1 = random.randint(2, 10)
    num2 = random.randint(2, 10)
    operators = ['+', '-', '*']
    operator = random.choice(operators)

    problem_string = f"{num1} {operator} {num2}"

    if operator == '+':
        correct_answer = num1 + num2
    elif operator == '-':
        correct_answer = num1 - num2
    else: # '*'
        correct_answer = num1 * num2

    problem_id = str(random.randint(100000, 999999))

    # Aufgabe in DynamoDB speichern
    item = {
        'problem_id': problem_id,
        'correct_answer': correct_answer,
        # Optional: Setze eine TTL (Time To Live), damit Einträge automatisch gelöscht werden
        # nach z.B. 5 Minuten (300 Sekunden)
        'ttl': int(os.time() + 300)
    }
    table.put_item(Item=item) # Speichere den Eintrag in der DynamoDB Tabelle

    return {"problem": problem_string, "problem_id": problem_id}


def check_math_answer(problem_id, user_answer):
    # Aufgabe aus DynamoDB abrufen
    response = table.get_item(Key={'problem_id': problem_id})
    item = response.get('Item')

    if item is None:
        # Das Problem wurde nicht in DynamoDB gefunden (entweder nie gespeichert oder TTL abgelaufen)
        return {"is_correct": False, "message": "Problem nicht gefunden oder abgelaufen."}

    correct_answer = item.get('correct_answer')

    is_correct = (user_answer == correct_answer)

    # Optional: Problem aus DynamoDB löschen, nachdem es geprüft wurde
    # table.delete_item(Key={'problem_id': problem_id})

    return {
        "is_correct": is_correct,
        "correct_answer": correct_answer
    }


# --- Ab hier ist Code, der nur für Lambda ist, nicht für Colab-Tests ---
def lambda_handler(event, context):
    path = event.get('path', '/')
    if path.startswith('/prod/'):
        path = path[len('/prod'):]

    http_method = event.get('httpMethod')

    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "OPTIONS,POST,GET"
    }

    if http_method == 'OPTIONS':
        return {'statusCode': 200, 'headers': headers}

    if path == '/problem' and http_method == 'GET':
        problem_data = generate_math_problem()
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps(problem_data)
        }

    elif path == '/check' and http_method == 'POST':
        try:
            body = json.loads(event.get('body', '{}'))
            problem_id = body.get('problem_id')
            user_answer = body.get('answer')

            if problem_id is None or user_answer is None:
                return {
                    'statusCode': 400,
                    'headers': headers,
                    'body': json.dumps({"error": "Fehlende ID oder Antwort."})
                }

            result = check_math_answer(problem_id, user_answer)

            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps(result)
            }
        except json.JSONDecodeError:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({"error": "Ungültiges JSON-Format."})
            }
        except Exception as e:
            # Für alle anderen Fehler
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({"error": f"Interner Serverfehler: {str(e)}"})
            }

    return {
        'statusCode': 404,
        'headers': headers,
        'body': json.dumps({"message": "Ressource nicht gefunden."})
    }