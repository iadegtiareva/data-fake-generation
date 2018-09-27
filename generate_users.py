from mimesis import Generic
import csv
path = input('Enter the csv filename (default: users_data.csv):  ') or "users_data.csv"
language = input('Enter the language (default: en):  ') or "en"
num_rows = input('Enter the number of rows (default: 100):  ') or "100"
num_rows = int(num_rows)
user = Generic (language)
def user_info():
    data = [
        user.person.identifier(mask='##-##/##'),
        user.person.username(template='U_d'),
        user.person.full_name(),
        user.person.age(),
        user.person.occupation(),
        user.address.city(),
        user.address.address(),
        user.address.postal_code(),
        user.person.favorite_music_genre(),
        user.person.favorite_movie(),
        user.person.email(domains=('gmail.com', 'mail.ru')),
        user.person.telephone(mask='', placeholder='#'),
        user.datetime.timestamp()
    ]
    return data

for _ in range(0, num_rows):
   with open(path, "a", newline='') as file:
      user_data = user_info()
      writer = csv.writer(file, delimiter=';')
      writer.writerow(user_data)
