import random
import json
import os
import boto3
import time # WICHTIG: Dieses Modul wird für time.time() benötigt

# Initialisiere den DynamoDB-Client außerhalb der Funktion
dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('DYNAMODB_TABLE_NAME', 'KopfrechnenAufgaben')
table = dynamodb.Table(table_name)

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
        # KORREKTUR: os.time() wurde zu time.time() geändert
        'ttl': int(time.time() + 300) # time.time() gibt die aktuelle Zeit in Sekunden seit der Epoche zurück
    }
    table.put_item(Item=item)

    return {"problem": problem_string, "problem_id": problem_id}


def check_math_answer(problem_id, user_answer):
    response = table.get_item(Key={'problem_id': problem_id})
    item = response.get('Item')

    if item is None:
        return {"is_correct": False, "message": "Problem nicht gefunden oder abgelaufen."}

    correct_answer = item.get('correct_answer')

    is_correct = (user_answer == correct_answer)

    table.delete_item(Key={'problem_id': problem_id})

    return {
        "is_correct": is_correct,
        "correct_answer": correct_answer
    }


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