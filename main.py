from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from pydantic import BaseModel
import models

app = FastAPI(title="Booking API Estetica")

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

class RichiestaSlot(BaseModel):
    telefono_cliente: str
    servizio_id: int
    data_ora_richiesta: datetime

class ConfermaPrenotazione(BaseModel):
    telefono_cliente: str
    nome_cliente: str
    servizio_id: int
    data_ora_richiesta: datetime

def verifica_disponibilita_slot(db: Session, servizio_id: int, inizio: datetime):
    servizio = db.query(models.Servizio).filter(models.Servizio.id == servizio_id).first()
    if not servizio:
        raise HTTPException(status_code=404, detail="Servizio non trovato")

    fine = inizio + timedelta(minutes=servizio.durata_minuti)

    sovrapposizioni = db.query(models.Prenotazione).filter(
        models.Prenotazione.inizio < fine,
        models.Prenotazione.fine > inizio
    ).all()

    return len(sovrapposizioni) == 0, inizio, fine, servizio

@app.get("/api/servizi")
def get_servizi(db: Session = Depends(get_db)):
    servizi = db.query(models.Servizio).all()
    return [{"id": s.id, "nome": s.nome, "durata": s.durata_minuti} for s in servizi]

@app.post("/api/whatsapp/verifica-slot")
def webhook_verifica_slot(richiesta: RichiestaSlot, db: Session = Depends(get_db)):
    disponibile, inizio, fine, servizio = verifica_disponibilita_slot(
        db, richiesta.servizio_id, richiesta.data_ora_richiesta
    )

    if disponibile:
        return {
            "disponibile": True,
            "messaggio": f"Lo slot per '{servizio.nome}' il {inizio.strftime('%d/%m/%Y alle %H:%M')} e' DISPONIBILE!"
        }
    else:
        return {
            "disponibile": False,
            "messaggio": f"Purtroppo l'orario delle {inizio.strftime('%H:%M')} non e' disponibile per '{servizio.nome}'."
        }

@app.post("/api/prenota")
def crea_prenotazione(dati: ConfermaPrenotazione, db: Session = Depends(get_db)):
    disponibile, inizio, fine, servizio = verifica_disponibilita_slot(
        db, dati.servizio_id, dati.data_ora_richiesta
    )

    if not disponibile:
        raise HTTPException(status_code=400, detail="Slot occupato! Scegli un altro orario.")

    utente = db.query(models.Utente).filter(models.Utente.telefono == dati.telefono_cliente).first()
    if not utente:
        utente = models.Utente(nome=dati.nome_cliente, telefono=dati.telefono_cliente)
        db.add(utente)
        db.commit()
        db.refresh(utente)

    nuova_prenotazione = models.Prenotazione(
        utente_id=utente.id,
        servizio_id=servizio.id,
        inizio=inizio,
        fine=fine
    )
    db.add(nuova_prenotazione)
    db.commit()

    return {"status": "ok", "messaggio": f"Prenotazione confermata per {servizio.nome}!"}

@app.get("/api/miei-appuntamenti/{telefono}")
def get_miei_appuntamenti(telefono: str, db: Session = Depends(get_db)):
    utente = db.query(models.Utente).filter(models.Utente.telefono == telefono).first()
    if not utente:
        return []

    appuntamenti = db.query(models.Prenotazione).filter(models.Prenotazione.utente_id == utente.id).all()
    
    risultato = []
    for app in appuntamenti:
        risultato.append({
            "id": app.id,
            "servizio": app.servizio.nome,
            "data_ora": app.inizio.strftime("%d/%m/%Y %H:%M"),
            "durata_minuti": app.servizio.durata_minuti
        })
    return risultato

# --- NUOVI ENDPOINT PER LA DASHBOARD ESTETISTA ---

@app.get("/api/admin/tutti-appuntamenti")
def get_tutti_appuntamenti(db: Session = Depends(get_db)):
    appuntamenti = db.query(models.Prenotazione).order_by(models.Prenotazione.inizio.asc()).all()
    
    risultato = []
    for app in appuntamenti:
        risultato.append({
            "id": app.id,
            "cliente_nome": app.utente.nome,
            "cliente_telefono": app.utente.telefono,
            "servizio": app.servizio.nome,
            "inizio": app.inizio.strftime("%d/%m/%Y %H:%M"),
            "fine": app.fine.strftime("%H:%M"),
            "durata_minuti": app.servizio.durata_minuti
        })
    return risultato

@app.delete("/api/admin/cancella/{appuntamento_id}")
def cancella_appuntamento(appuntamento_id: int, db: Session = Depends(get_db)):
    appuntamento = db.query(models.Prenotazione).filter(models.Prenotazione.id == appuntamento_id).first()
    if not appuntamento:
        raise HTTPException(status_code=404, detail="Appuntamento non trovato")
    
    db.delete(appuntamento)
    db.commit()
    return {"status": "ok", "messaggio": "Appuntamento cancellato con successo!"}

# Pagine Web
@app.get("/")
def mostra_pagina_web():
    return FileResponse("index.html")

@app.get("/dashboard")
def mostra_dashboard():
    return FileResponse("dashboard.html")