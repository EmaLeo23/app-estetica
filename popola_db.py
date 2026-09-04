import models

db = models.SessionLocal()

db.query(models.Servizio).delete()

servizi_estetica = [
    models.Servizio(nome="Pulizia del viso profonda", durata_minuti=60, prezzo=0),
    models.Servizio(nome="Trattamento viso anti-age / idratante", durata_minuti=45, prezzo=0),
    models.Servizio(nome="Manicure base / con smalto tradizionale", durata_minuti=30, prezzo=0),
    models.Servizio(nome="Manicure con smalto semipermanente", durata_minuti=60, prezzo=0),
    models.Servizio(nome="Ricostruzione unghie in gel", durata_minuti=90, prezzo=0),
    models.Servizio(nome="Pedicure estetica / curativa", durata_minuti=45, prezzo=0),
    models.Servizio(nome="Epilazione cera gambe e bikini", durata_minuti=30, prezzo=0),
    models.Servizio(nome="Epilazione cera zone piccole (baffetti/sopracciglia)", durata_minuti=15, prezzo=0),
    models.Servizio(nome="Massaggio corpo (drenante / rilassante / modellante)", durata_minuti=60, prezzo=0),
    models.Servizio(nome="Laminazione ciglia e sopracciglia", durata_minuti=60, prezzo=0),
    models.Servizio(nome="Trucco giorno / sera", durata_minuti=45, prezzo=0),
]

for servizio in servizi_estetica:
    db.add(servizio)

db.commit()
db.close()
print("Listino estetico inserito con successo!")