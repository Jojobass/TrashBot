"""Various actions with DB

python dbactions.py order <id> - show order by id
python dbactions.py worker <username-like> - show all orders by worker
python dbactions.py worker month <username-like> -
show all order by worker for last month
"""
import sqlite3
import sys


def print_row(row):
    print(
        '|'.join([str(row[0]).ljust(6), row[1].ljust(16),
                  row[2].ljust(15), row[3].ljust(30), row[4].ljust(12),
                  row[5].ljust(30), row[6].ljust(30), row[7].ljust(16),
                  row[8].ljust(25), row[9].ljust(20)])
    )

def print_header():
    print(
        '|'.join(['id'.ljust(6), 'username'.ljust(16), 'name'.ljust(15),
                  'address'.ljust(30), 'phone'.ljust(12),
                  'comment'.ljust(30), 'service'.ljust(30),
                  'worker'.ljust(16), 'status'.ljust(25),
                  'date'.ljust(20)])
    )
    print('-' * 209)

def main(args):
    conn = sqlite3.connect(r'trashbotDB.db')
    if len(args) >= 3 and args[1] == 'order':
        sql = ('SELECT '
               'id, '
               'customer_username, '
               'name, '
               'address, '
               'phone, '
               'comment, '
               'service, '
               'worker_username, '
               'status, '
               'datetime(order_datetime, "unixepoch", "+3 hours") '
               f'FROM order_info WHERE id = {args[2]};')
        cur = conn.cursor()
        cur.execute(sql)
        row = cur.fetchone()
        if row is None:
            print('None')
        else:
            print_header()
            print_row(row)
    if len(args) >= 3 and args[1] == 'worker':
        sql = ''
        if args[2] == 'month' and len(args) >= 4:
            sql = ('SELECT '
                   'id, '
                   'customer_username, '
                   'name, '
                   'address, '
                   'phone, '
                   'comment, '
                   'service, '
                   'worker_username, '
                   'status, '
                   'datetime(order_datetime, "unixepoch", "+3 hours") '
                   f'FROM order_info '
                   f'WHERE worker_username LIKE "%{args[3]}%" '
                   f'AND order_datetime > '
                   f'strftime("%s","now", "start of day", "-1 months");')
        else:
            sql = ('SELECT '
                   'id, '
                   'customer_username, '
                   'name, '
                   'address, '
                   'phone, '
                   'comment, '
                   'service, '
                   'worker_username, '
                   'status, '
                   'datetime(order_datetime, "unixepoch", "+3 hours") '
                   f'FROM order_info WHERE worker_username LIKE "%{args[2]}%";')
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        if len(rows) == 0:
            print('None')
        else:
            print('Total orders:', len(rows))
            print_header()
            for row in rows:
                print_row(row)



if __name__ == '__main__':
    main(sys.argv)
