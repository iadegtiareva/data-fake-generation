from mimesis import Generic
import csv

MUSIC_GENRES = [
    "Rock", "Pop", "Jazz", "Blues", "Classical",
    "Hip Hop", "Electronic", "Country", "Reggae", "Folk",
    "Metal", "Punk", "Soul", "Funk", "Disco",
    "House", "Techno", "Ambient", "Ska", "Gospel",
]
MOVIES = [
    "The Shawshank Redemption", "The Godfather", "The Dark Knight",
    "Pulp Fiction", "Forrest Gump", "Inception", "The Matrix",
    "Interstellar", "Spirited Away", "The Lion King", "Back to the Future",
    "Jurassic Park", "Toy Story", "WALL-E", "Finding Nemo", "Coco",
    "Ratatouille", "The Truman Show", "Groundhog Day", "The Grand Budapest Hotel",
]

path = input('Enter the csv filename (default: users_data.csv):  ') or "users_data.csv"
language = input('Enter the language (default: en):  ') or "en"
num_rows = input('Enter the number of rows (default: 100):  ') or "100"
num_rows = int(num_rows)
user = Generic (language)
def user_info():
    data = [
        user.person.identifier(mask='##-##/##'),
        user.person.username(mask='U_d'),
        user.person.full_name(),
        user.person.random.randint(16, 90),
        user.person.occupation(),
        user.address.city(),
        user.address.address(),
        user.address.postal_code(),
        user.random.choice(MUSIC_GENRES),
        user.random.choice(MOVIES),
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
