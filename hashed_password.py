import bcrypt
password = bcrypt.hashpw("myscapeadmin@01".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
print(password)
