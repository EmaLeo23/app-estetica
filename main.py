from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, date
from pydantic import BaseModel
import json
import models

app = FastAPI(title="Booking API Advanced Multi-Staff")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = models.SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_config(db: Session):
    config = db.query(models.ImpostazioniSalone).first()
    if not config:
        config = models.ImpostazioniSalone()
        db.add(config)
        db.commit()
        db.refresh(config)
    return config

class ConfermaPrenotazione(BaseModel):
    telefono_cliente: str
    nome_cliente: str
    pin: str
    servizio_id: int
    data_ora_richiesta: datetime

class SpostamentoAppuntamento(BaseModel):
    nuovo_inizio: datetime
    operatrice: str = "Non Assegnata"

class AssegnaOperatriceRequest(BaseModel):
    operatrice: str

class ImpostazioniRequest(BaseModel):
    num_operatrici: int
    logo_url: str
    orari_settimana: dict

class RichiestaMieiAppuntamenti(BaseModel):
    telefono: str
    pin: str

class ResetPinRequest(BaseModel):
    telefono: str
    nuovo_pin: str

def valida_slot_15_minuti(dt: datetime):
    if dt.minute % 15 != 0 or dt.second != 0:
        raise HTTPException(status_code=400, detail="Gli orari devono essere a scatti di 15 minuti.")

def verifica_disponibilita_slot(db: Session, servizio_id: int, inizio: datetime, escludi_id: int = None):
    valida_slot_15_minuti(inizio)

    if inizio.date() <= date.today():
        raise HTTPException(status_code=400, detail="Non e' possibile prenotare per il giorno stesso o per date passate.")

    config = get_config(db)
    orari_dict = json.loads(config.orari_settimana)

    # Convertiamo il giorno della settimana (0=Domenica, 1=Lunedì, ..., 6=Sabato)
    weekday_idx = str((inizio.weekday() + 1) % 7)
    info_giorno = orari_dict.get(weekday_idx, {"aperto": False})

    if not info_giorno.get("aperto"):
        raise HTTPException(status_code=400, detail="Il centro estetico e' chiuso nel giorno selezionato.")

    ora_inizio_str = inizio.strftime("%H:%M")
    
    in_mattina = False
    if info_giorno.get("am_a") and info_giorno.get("am_c"):
        in_mattina = info_giorno["am_a"] <= ora_inizio_str < info_giorno["am_c"]

    in_pomeriggio = False
    if info_giorno.get("pm_a") and info_giorno.get("pm_c"):
        in_pomeriggio = info_giorno["pm_a"] <= ora_inizio_str < info_giorno["pm_c"]

    if not (in_mattina or in_pomeriggio):
        raise HTTPException(status_code=400, detail="Orario fuori dai turni lavorativi o in pausa pranzo.")

    servizio = db.query(models.Servizio).filter(models.Servizio.id == servizio_id).first()
    if not servizio:
        raise HTTPException(status_code=404, detail="Servizio non trovato")

    fine = inizio + timedelta(minutes=servizio.durata_minuti)

    query = db.query(models.Prenotazione).filter(
        models.Prenotazione.inizio < fine,
        models.Prenotazione.fine > inizio
    )
    if escludi_id:
        query = query.filter(models.Prenotazione.id != escludi_id)

    sovrapposizioni = query.count()
    disponibile = sovrapposizioni < config.num_operatrici

    return disponibile, inizio, fine, servizio

@app.get("/api/servizi")
def get_servizi(db: Session = Depends(get_db)):
    servizi = db.query(models.Servizio).all()
    return [{"id": s.id, "nome": s.nome, "durata": s.durata_minuti} for s in servizi]

@app.get("/api/config")
def get_impostazioni(db: Session = Depends(get_db)):
    config = get_config(db)
    return {
        "num_operatrici": config.num_operatrici,
        "logo_url": config.logo_url,
        "orari_settimana": json.loads(config.orari_settimana)
    }

@app.post("/api/admin/config")
def salva_impostazioni(dati: ImpostazioniRequest, db: Session = Depends(get_db)):
    config = get_config(db)
    config.num_operatrici = dati.num_operatrici
    config.logo_url = dati.logo_url
    config.orari_settimana = json.dumps(dati.orari_settimana)
    db.commit()
    return {"status": "ok", "messaggio": "Impostazioni aggiornate con successo!"}

@app.post("/api/prenota")
def crea_prenotazione(dati: ConfermaPrenotazione, db: Session = Depends(get_db)):
    if len(dati.pin) != 4 or not dati.pin.isdigit():
        raise HTTPException(status_code=400, detail="Il PIN deve essere composto da 4 cifre.")

    disponibile, inizio, fine, servizio = verifica_disponibilita_slot(
        db, dati.servizio_id, dati.data_ora_richiesta
    )

    if not disponibile:
        raise HTTPException(status_code=400, detail="Tutte le operatrici sono occupate in questo orario!")

    utente = db.query(models.Utente).filter(models.Utente.telefono == dati.telefono_cliente).first()
    if not utente:
        utente = models.Utente(nome=dati.nome_cliente, telefono=dati.telefono_cliente, pin=dati.pin)
        db.add(utente)
        db.commit()
        db.refresh(utente)
    else:
        if utente.pin != dati.pin:
            raise HTTPException(status_code=401, detail="PIN errato per questo numero di telefono!")

    nuova_prenotazione = models.Prenotazione(
        utente_id=utente.id,
        servizio_id=servizio.id,
        inizio=inizio,
        fine=fine,
        stato="in_attesa",
        operatrice="Non Assegnata"
    )
    db.add(nuova_prenotazione)
    db.commit()

    return {
        "status": "ok", 
        "messaggio": f"Richiesta inviata! La prenotazione per {servizio.nome} e' in attesa di conferma."
    }

@app.post("/api/miei-appuntamenti")
def get_miei_appuntamenti(richiesta: RichiestaMieiAppuntamenti, db: Session = Depends(get_db)):
    utente = db.query(models.Utente).filter(models.Utente.telefono == richiesta.telefono).first()
    if not utente:
        raise HTTPException(status_code=404, detail="Nessun utente trovato.")

    if utente.pin != richiesta.pin:
        raise HTTPException(status_code=401, detail="PIN errato!")

    appuntamenti = db.query(models.Prenotazione).filter(models.Prenotazione.utente_id == utente.id).order_by(models.Prenotazione.inizio.desc()).all()
    
    risultato = []
    for app in appuntamenti:
        risultato.append({
            "id": app.id,
            "servizio": app.servizio.nome,
            "data_ora": app.inizio.strftime("%d/%m/%Y %H:%M"),
            "durata_minuti": app.servizio.durata_minuti,
            "stato": app.stato,
            "operatrice": app.operatrice
        })
    return risultato

@app.post("/api/appuntamenti/{id}/accetta-spostamento")
def accetta_spostamento(id: int, db: Session = Depends(get_db)):
    app = db.query(models.Prenotazione).filter(models.Prenotazione.id == id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Appuntamento non trovato")
    app.stato = "confermato"
    db.commit()
    return {"status": "ok"}

# --- ENDPOINT ADMIN ---

@app.get("/api/admin/tutti-appuntamenti")
def get_tutti_appuntamenti(db: Session = Depends(get_db)):
    appuntamenti = db.query(models.Prenotazione).order_by(models.Prenotazione.inizio.asc()).all()
    
    risultato = []
    for app in appuntamenti:
        risultato.append({
            "id": app.id,
            "cliente_nome": app.utente.nome,
            "cliente_telefono": app.utente.telefono,
            "cliente_pin": app.utente.pin,
            "servizio": app.servizio.nome,
            "servizio_id": app.servizio_id,
            "inizio": app.inizio.strftime("%d/%m/%Y %H:%M"),
            "fine": app.fine.strftime("%H:%M"),
            "durata_minuti": app.servizio.durata_minuti,
            "stato": app.stato or "in_attesa",
            "operatrice": app.operatrice or "Non Assegnata"
        })
    return risultato

@app.post("/api/admin/conferma/{id}")
def conferma_appuntamento(id: int, db: Session = Depends(get_db)):
    app = db.query(models.Prenotazione).filter(models.Prenotazione.id == id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Appuntamento non trovato")
    app.stato = "confermato"
    db.commit()
    return {"status": "ok"}

@app.put("/api/admin/assegna-operatrice/{id}")
def assegna_operatrice(id: int, dati: AssegnaOperatriceRequest, db: Session = Depends(get_db)):
    app = db.query(models.Prenotazione).filter(models.Prenotazione.id == id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Appuntamento non trovato")
    app.operatrice = dati.operatrice
    db.commit()
    return {"status": "ok"}

@app.put("/api/admin/sposta/{id}")
def sposta_appuntamento(id: int, dati: SpostamentoAppuntamento, db: Session = Depends(get_db)):
    app = db.query(models.Prenotazione).filter(models.Prenotazione.id == id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Appuntamento non trovato")
    
    disponibile, inizio, fine, _ = verifica_disponibilita_slot(
        db, app.servizio_id, dati.nuovo_inizio, escludi_id=id
    )
    if not disponibile:
        raise HTTPException(status_code=400, detail="Nuovo orario occupato!")

    app.inizio = inizio
    app.fine = fine
    app.stato = "spostato"
    if dati.operatrice:
        app.operatrice = dati.operatrice
    db.commit()
    return {"status": "ok"}

@app.delete("/api/admin/cancella/{id}")
def cancella_appuntamento(id: int, db: Session = Depends(get_db)):
    app = db.query(models.Prenotazione).filter(models.Prenotazione.id == id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Appuntamento non trovato")
    db.delete(app)
    db.commit()
    return {"status": "ok"}

@app.post("/api/admin/reset-pin")
def reset_pin_utente(dati: ResetPinRequest, db: Session = Depends(get_db)):
    utente = db.query(models.Utente).filter(models.Utente.telefono == dati.telefono).first()
    if not utente:
        raise HTTPException(status_code=404, detail="Utente non trovato.")
    utente.pin = dati.nuovo_pin
    db.commit()
    return {"status": "ok"}

@app.get("/")
def mostra_pagina_web():
    return FileResponse("index.html")

@app.get("/dashboard")
def mostra_dashboard():
    return FileResponse("dashboard.html")