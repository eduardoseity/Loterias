from flask import Flask, request
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json

app = Flask(__name__)
CORS(app, supports_credentials=True)
app.config['CORS_HEADERS'] = 'Content-Type'

lottery = ''

@app.route('/lotofacil')
def lotofacil():
    lottery_config = {
        'min_bet': 15,
        'max_bet': 20,
        'minor_number': 1,
        'major_number': 25,
        'prizes': [11,12,13,14,15],
        'bet_prices': {
            '15': 2.5,
            '16': 40,
            '17': 340,
            '18': 2040,
            '19': 9690,
            '20': 38760
        },
        'first_ball_column': 2,
        'draw_number_column': 0
    }
    global lottery
    lottery = Lottery('Lotofacil', lottery_config)
    return json.dumps(lottery_config)

@app.route('/megasena')
def megasena():
    lottery_config = {
        'min_bet': 6,
        'max_bet': 15,
        'minor_number': 1,
        'major_number': 60,
        'prizes': [5,4],
        'bet_prices': {
            '6': 4.5,
            '7': 31.5,
            '8': 126,
            '9': 378,
            '10': 945,
            '11': 2079,
            '12': 4158,
            '13': 7722,
            '14': 13513.5,
            '15': 22522.5
        },
        'first_ball_column': 2,
        'draw_number_column': 0
    }
    global lottery
    lottery = Lottery('Mega-Sena', lottery_config)
    return json.dumps(lottery_config)

@app.route('/addGame', methods=['POST'])
def add_game():
    numbers = request.get_json()['numbers'].split(',')
    numbers.remove('')
    numbers = [int(i) for i in numbers]
    try:
        games = lottery.add_game(numbers)
    except Exception as e:
        return e.args[0]
    return games

@app.route('/getGames')
def get_games():
    games = lottery.get_games()
    return json.dumps(games)

@app.route('/checkResults', methods=['POST'])
def check_results():
    mode = request.get_json()['mode']
    if mode == 'last':
        return lottery.check_last_result(lottery.get_games())
    elif mode == 'all':
        return lottery.check_all_results(lottery.get_games())

@app.route('/deleteGame', methods=['GET'])
def delete_game():
    game_list = lottery.delete_game(int(request.args['index']))
    return json.dumps(game_list)

class Lottery:
    def __init__(self, loto_name, lottery_config):
        self.__base_url = 'https://servicebus2.caixa.gov.br/portaldeloterias/api/resultados?modalidade='
        self.__url = self.__base_url + loto_name
        self.__lottery_config = lottery_config
        '''
            lottery_config = {
                min_bet: minimal numbers quantity to bet,
                max_bet: maximum numbers quantity to bet,
                minor_number: the minor number possible,
                major_number: the major number possible,
                prizes: the quantity of numbers to receive a prize. ie [11,12,13,14,15],
                bet_prices: the prices of each bet. ie [2.5, 40, 340, 2040, 9690, 38760],
                first_ball_column: index column of the first ball,
                draw_number_column: the number of draw lottery
            }
        '''
        self.__results_table = ''
        self.__games = []

        self.__validade_rules()
        self.__get_results()
    
    def __validade_rules(self):
        if type(self.__lottery_config) != dict: raise TypeError('Only dictionary type is allowed in lottery_config parameter')
        
        for rule in ['min_bet', 'max_bet', 'prizes', 'bet_prices', 'first_ball_column', 'draw_number_column', 'minor_number', 'major_number']:
            if (rule in self.__lottery_config) == False: raise KeyError(f'The key {rule} is missing in lottery_config dictionary')

    def __get_results(self):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.41 Safari/537.36 Edg/101.0.1210.32',
            'Content-Type': '*/*'
        }
        response = requests.get(self.__url, headers=headers, stream=True)
        if response.status_code != 200: raise Exception('Error in http response')

        soup = BeautifulSoup(response.json()['html'], 'lxml')
        main_table = soup.table
        for t in main_table.find_all('table'):
            t.replace_with('')
        
        self.__results_table = pd.read_html(str(main_table))[0]

    def get_last_result(self):
        result = self.__results_table.tail(1)
        result_list = [result.iloc[:,ball].values[0] for ball in range(self.__lottery_config['first_ball_column'], self.__lottery_config['first_ball_column'] + self.__lottery_config['min_bet'])]
        return [(result.iloc[:,self.__lottery_config['draw_number_column']].values[0],result_list)]

    def get_all_results(self):
        results = []
        for result in self.__results_table.itertuples():
            results.append((result[self.__lottery_config['draw_number_column']+1], [result[ball] for ball in range(self.__lottery_config['first_ball_column']+1, self.__lottery_config['first_ball_column']+ 1 + self.__lottery_config['min_bet'])]))
        
        return results

    def check_results(self, result_list, picked_list):
        results_df_list = []

        for result in result_list:
            game = 0
            for picked in picked_list:
                match = 0
                game += 1
                for number in picked:
                    if (number in result[1]) == True: match += 1
                results_df_list.append([result[0], game, match]) 
        
        results_df = pd.DataFrame(results_df_list, columns=['Draw_Number', 'Game_Number', 'Matches'])
        results_df.sort_values(by=['Matches'], ascending=False, inplace=True)
        
        return results_df.to_html(None)

    def add_game(self, numbers):
        if len(numbers) > self.__lottery_config['max_bet'] or len(numbers) < self.__lottery_config['min_bet']: raise ValueError('Quantity of numbers out of bound')

        for n in numbers:
            if n < self.__lottery_config['minor_number'] or n > self.__lottery_config['major_number']: 
                raise ValueError(f'Number is out of bound. ({self.__lottery_config["minor_number"]} to {self.__lottery_config["major_number"]})')
            
        self.__games.append(numbers)

        return json.dumps(self.__games)

    def delete_game(self, index):
        del self.__games[index]
        return self.__games

    def get_games(self):
        return self.__games

    def check_last_result(self, picked_list):
        return self.check_results(self.get_last_result(), picked_list)

    def check_all_results(self, picked_list):
        return self.check_results(self.get_all_results(), picked_list)

if __name__ == '__main__':
    app.run(debug=True, host='localhost', port=4444)