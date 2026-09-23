from mimesis import Generic
from mimesis.locales import Locale
import csv
import sys
from pathlib import Path

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

def fail(message):
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def user_info(user):
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


def main():
    output_started = False
    try:
        try:
            path = input('Enter the csv filename (default: users_data.csv):  ') or "users_data.csv"
            language = input('Enter the language (default: en):  ').strip().lower() or "en"
            num_rows = input('Enter the number of rows (default: 100):  ').strip() or "100"
        except EOFError:
            fail("input ended before all parameters were provided.")

        try:
            num_rows = int(num_rows)
        except ValueError:
            fail("count must be an integer >= 0.")
        if num_rows < 0:
            fail("count must be an integer >= 0.")

        try:
            language = Locale(language)
        except ValueError:
            fail(f"unsupported locale: {language!r}.")

        if not path.strip() or '\x00' in path:
            fail("path must be non-blank and contain no null characters.")
        output_path = Path(path)
        try:
            if not output_path.parent.is_dir():
                fail(f"path parent is not an existing directory: {str(output_path.parent)!r}.")
            if (output_path.exists() or output_path.is_symlink()) and not output_path.is_file():
                fail(f"path is not a regular file: {path!r}.")
        except OSError as error:
            fail(f"cannot check path {path!r}: {error}")

        if num_rows == 0:
            print("Requested 0 records; file unchanged.")
            sys.exit(0)

        user = Generic(language)
        for _ in range(num_rows):
            user_data = user_info(user)
            try:
                file = open(path, "a", newline='')
            except OSError as error:
                fail(f"cannot open CSV path {path!r} for appending: {error}")
            output_started = True
            try:
                with file:
                    writer = csv.writer(file, delimiter=';')
                    writer.writerow(user_data)
            except OSError as error:
                fail(f"cannot write CSV {path!r}: {error}. Output may be incomplete.")
            except UnicodeEncodeError as error:
                fail(f"cannot encode CSV data for {path!r}: {error}. Output may be incomplete.")
            except csv.Error as error:
                fail(f"cannot serialize CSV data for {path!r}: {error}. Output may be incomplete.")
    except KeyboardInterrupt:
        message = "Interrupted by user."
        if output_started:
            message += " Output may be incomplete."
        print(message, file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
