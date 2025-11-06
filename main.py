from flask import Flask, render_template
import sqlite3

app = Flask(__name__) # 인스턴스 하나 만듦. 

@app.route('/')
@app.route('/restaruants/')
def showRestaurants():
    #return "Show all restaruants"
    db = sqlite3.connect('restaurant_menu.db') #local 하게 사용하기 때문에 파일이름. 외부 데이터베이스 사용할시 주소적어주면 된다
    db.row_factory = sqlite3.Row
    cursor = db.cursor()
    items = cursor.execute(
        'select id, name from restaurant'
    ).fetchall()
    return render_template('restaurant.html',items=items)
    # output = ''
    # for item in items:
    #     output += f"{item['name']}"
    #     output += '<br>'
        
    # return output

@app.route('/restaurants/new/')
def newRestaurants():
    return "add a new restaurants"



# @app.route('/') # 127.0.0.1:5000/ 을 하면 앱 실행.
# @app.route('/hello/')
# @app.route('/hello/<string:name>/')
# def hello_web(name=None):
#     #return '<h1> Hello, web App!! </h1>' if name==None else f'<h1> Hello, {name}!! </h1>' 
#     return render_template('hello.html', name=name)


if __name__ == '__main__':
    app.debug=True
    app.run(host='127.0.0.1', port=5000)