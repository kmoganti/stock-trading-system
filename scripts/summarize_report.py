import json

def main():
    d = json.load(open('reports/nifty100_strategy_summary.json'))
    for k, v in d['results'].items():
        print(k + ': signals=' + str(len(v['signals'])) + ', no_data=' + str(len(v['no_data'])) + ', errors=' + str(len(v['errors'])))

if __name__ == '__main__':
    main()
