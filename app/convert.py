import csv

# Load book number -> name
books = {}
with open("key_english.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        books[row["b"]] = row["n"]  # adjust column names if different — check the CSV header first

# Convert verses into pipe format
with open("t_kjv.csv", encoding="utf-8") as f, open("kjv.txt", "w", encoding="utf-8") as out:
    for row in csv.DictReader(f):
        book_name = books.get(row["b"], row["b"])
        out.write(f"{book_name}|{row['c']}|{row['v']}|{row['t']}\n")

print("Done — wrote kjv.txt")
