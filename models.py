from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

Base = declarative_base()

class Servizio(Base):
    __tablename__ = "servizi"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, unique=True, index=True)
    durata_minuti = Column(Integer)
    prezzo = Column(Integer)

class Utente(Base):
    __tablename__ = "utenti"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String)
    telefono = Column(String, unique=True, index=True)
    pin = Column(String, nullable=False)

class ImpostazioniSalone(Base):
    __tablename__ = "impostazioni"
    id = Column(Integer, primary_key=True)
    nomi_operatori = Column(String, default="Elena, Lucia")
    logo_url = Column(String, default="")
    orari_settimana = Column(String, default='{"0":{"aperto":false,"am_a":"","am_c":"","pm_a":"","pm_c":""},"1":{"aperto":false,"am_a":"","am_c":"","pm_a":"","pm_c":""},"2":{"aperto":true,"am_a":"08:30","am_c":"12:30","pm_a":"14:30","pm_c":"19:30"},"3":{"aperto":true,"am_a":"08:30","am_c":"12:30","pm_a":"14:30","pm_c":"19:30"},"4":{"aperto":true,"am_a":"08:30","am_c":"12:30","pm_a":"14:30","pm_c":"19:30"},"5":{"aperto":true,"am_a":"08:30","am_c":"12:30","pm_a":"14:30","pm_c":"19:30"},"6":{"aperto":true,"am_a":"08:30","am_c":"12:30","pm_a":"14:30","pm_c":"19:30"}}')

class Prenotazione(Base):
    __tablename__ = "prenotazioni"
    id = Column(Integer, primary_key=True, index=True)
    utente_id = Column(Integer, ForeignKey("utenti.id"))
    servizio_id = Column(Integer, ForeignKey("servizi.id"))
    inizio = Column(DateTime, index=True)
    fine = Column(DateTime, index=True)
    stato = Column(String, default="in_attesa")
    operatore = Column(String, default="Non Assegnato")

    utente = relationship("Utente")
    servizio = relationship("Servizio")

engine = create_engine("sqlite:///./appuntamenti.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)