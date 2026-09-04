import os
import secrets
import json
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel

import models

app = FastAPI(title="Booking API Advanced Multi-Staff")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBasic()
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "estetica2026")

def verifica_credenziali_admin(credentials: HTTPBasicCredentials = Depends(security)):
    utente_corretto = secrets.compare_digest(credentials.username, ADMIN_USER)
    password_corretta = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    if not (utente_corretto and password_corretta):
        raise HTTPException(
            status_code=401,
            detail="Credenziali non valide.",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

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
    operatore: Optional[str] = None

class AssegnaOperatoreRequest(BaseModel):
    operatore: str

class ImpostazioniRequest(BaseModel):
    nomi_operatori: str
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

def valida_pin(pin: str):
    if len(pin) != 4 or not pin.isdigit():
        raise HTTPException(status_code=400, detail="Il PIN deve essere composto da 4 cifre.")

def verifica_disponibilita_slot(db: Session, servizio_id: int, inizio: datetime, escludi_id: int = None):
    valida_slot_15_minuti(inizio)

    config = get_config(db)
    orari_dict = json.loads(config.orari_settimana)

    weekday_idx = str((inizio.weekday() + 1) % 7)
    info_giorno = orari_dict.get(weekday_idx, {"aperto": False})

    if not info_giorno.get("aperto"):
        raise HTTPException(status_code=400, detail="Il centro e' chiuso nel giorno selezionato.")

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
    list_operatori = [op.strip() for op in config.nomi_operatori.split(',') if op.strip()]
    capienza_massima = max(len(list_operatori), 1)

    disponibile = sovrapposizioni < capienza_massima

    return disponibile, inizio, fine, servizio

@app.get("/api/servizi")
def get_servizi(db: Session = Depends(get_db)):
    servizi = db.query(models.Servizio).all()
    return [{"id": s.id, "nome": s.nome, "durata": s.durata_minuti} for s in servizi]

@app.get("/api/config")
def get_impostazioni(db: Session = Depends(get_db)):
    config = get_config(db)
    orari = json.loads(config.orari_settimana) if config.orari_settimana else {}
    return {
        "nomi_operatori": config.nomi_operatori,
        "logo_url": config.logo_url,
        "orari_settimana": orari
    }

@app.post("/api/admin/config")
def salva_impostazioni(
    dati: ImpostazioniRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verifica_credenziali_admin),
):
    config = get_config(db)
    config.nomi_operatori = dati.nomi_operatori
    config.logo_url = dati.logo_url
    config.orari_settimana = json.dumps(dati.orari_settimana)
    db.commit()
    return {"status": "ok", "messaggio": "Impostazioni salvate!"}

@app.post("/api/prenota")
def crea_prenotazione(dati: ConfermaPrenotazione, db: Session = Depends(get_db)):
    valida_pin(dati.pin)

    disponibile, inizio, fine, servizio = verifica_disponibilita_slot(
        db, dati.servizio_id, dati.data_ora_richiesta
    )

    if not disponibile:
        raise HTTPException(status_code=400, detail="Tutti gli operatori sono occupati in questo orario!")

    utente = db.query(models.Utente).filter(models.Utente.telefono == dati.telefono_cliente).first()
    if not utente:
        utente = models.Utente(nome=dati.nome_cliente, telefono=dati.telefono_cliente, pin=dati.pin)
        db.add(utente)
        db.commit()
        db.refresh(utente)
    else:
        if utente.pin != dati.pin:
            raise HTTPException(status_code=401, detail="PIN errato!")

    nuova_prenotazione = models.Prenotazione(
        utente_id=utente.id,
        servizio_id=servizio.id,
        inizio=inizio,
        fine=fine,
        stato="in_attesa",
        operatore="Non Assegnato"
    )
    db.add(nuova_prenotazione)
    db.commit()
    db.refresh(nuova_prenotazione)

    return {
        "status": "ok",
        "messaggio": f"Richiesta per {servizio.nome} inviata.",
        "id": nuova_prenotazione.id,
    }

@app.post("/api/miei-appuntamenti")
def get_miei_appuntamenti(richiesta: RichiestaMieiAppuntamenti, db: Session = Depends(get_db)):
    utente = db.query(models.Utente).filter(models.Utente.telefono == richiesta.telefono).first()
    if not utente or utente.pin != richiesta.pin:
        raise HTTPException(status_code=401, detail="Credenziali errate.")

    appuntamenti = db.query(models.Prenotazione).filter(
        models.Prenotazione.utente_id == utente.id
    ).order_by(models.Prenotazione.inizio.desc()).all()

    return [{
        "id": app.id,
        "servizio": app.servizio.nome,
        "data_ora": app.inizio.strftime("%d/%m/%Y %H:%M"),
        "durata_minuti": app.servizio.durata_minuti,
        "stato": app.stato,
        "operatore": app.operatore
    } for app in appuntamenti]

@app.post("/api/appuntamenti/{id}/accetta-spostamento")
def accetta_spostamento_cliente(id: int, db: Session = Depends(get_db)):
    app_ = db.query(models.Prenotazione).filter(models.Prenotazione.id == id).first()
    if not app_:
        raise HTTPException(status_code=404, detail="Appuntamento non trovato.")
    app_.stato = "confermato"
    db.commit()
    return {"status": "ok"}

@app.get("/api/admin/tutti-appuntamenti")
def get_tutti_appuntamenti(db: Session = Depends(get_db), _: str = Depends(verifica_credenziali_admin)):
    appuntamenti = db.query(models.Prenotazione).order_by(models.Prenotazione.inizio.asc()).all()
    return [{
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
        "operatore": app.operatore or "Non Assegnato"
    } for app in appuntamenti]

@app.post("/api/admin/conferma/{id}")
def conferma_appuntamento(id: int, db: Session = Depends(get_db), _: str = Depends(verifica_credenziali_admin)):
    app_ = db.query(models.Prenotazione).filter(models.Prenotazione.id == id).first()
    if not app_:
        raise HTTPException(status_code=404, detail="Appuntamento non trovato.")
    app_.stato = "confermato"
    db.commit()
    return {"status": "ok"}

@app.put("/api/admin/assegna-operatore/{id}")
def assegna_operatore(
    id: int,
    dati: AssegnaOperatoreRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verifica_credenziali_admin),
):
    app_ = db.query(models.Prenotazione).filter(models.Prenotazione.id == id).first()
    if not app_:
        raise HTTPException(status_code=404, detail="Appuntamento non trovato.")
    app_.operatore = dati.operatore
    db.commit()
    return {"status": "ok"}

@app.put("/api/admin/sposta/{id}")
def sposta_appuntamento(
    id: int,
    dati: SpostamentoAppuntamento,
    db: Session = Depends(get_db),
    _: str = Depends(verifica_credenziali_admin),
):
    app_ = db.query(models.Prenotazione).filter(models.Prenotazione.id == id).first()
    if not app_:
        raise HTTPException(status_code=404, detail="Appuntamento non trovato.")

    disponibile, inizio, fine, _s = verifica_disponibilita_slot(db, app_.servizio_id, dati.nuovo_inizio, escludi_id=id)
    if not disponibile:
        raise HTTPException(status_code=400, detail="Slot occupato")

    app_.inizio = inizio
    app_.fine = fine
    app_.stato = "spostato"
    if dati.operatore is not None:
        app_.operatore = dati.operatore
    db.commit()
    return {"status": "ok"}

@app.delete("/api/admin/cancella/{id}")
def cancella_appuntamento(id: int, db: Session = Depends(get_db), _: str = Depends(verifica_credenziali_admin)):
    app_ = db.query(models.Prenotazione).filter(models.Prenotazione.id == id).first()
    if not app_:
        raise HTTPException(status_code=404, detail="Appuntamento non trovato.")
    db.delete(app_)
    db.commit()
    return {"status": "ok"}

@app.post("/api/admin/reset-pin")
def reset_pin_utente(
    dati: ResetPinRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verifica_credenziali_admin),
):
    valida_pin(dati.nuovo_pin)
    utente = db.query(models.Utente).filter(models.Utente.telefono == dati.telefono).first()
    if not utente:
        raise HTTPException(status_code=404, detail="Cliente non trovato.")
    utente.pin = dati.nuovo_pin
    db.commit()
    return {"status": "ok"}

@app.get("/")
def mostra_pagina_web():
    return FileResponse("index.html")

@app.get("/dashboard")
def mostra_dashboard(_: str = Depends(verifica_credenziali_admin)):
    return FileResponse("dashboard.html")