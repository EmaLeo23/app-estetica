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

class Prenotazione(Base):
    __tablename__ = "prenotazioni"
    id = Column(Integer, primary_key=True, index=True)
    utente_id = Column(Integer, ForeignKey("utenti.id"))
    servizio_id = Column(Integer, ForeignKey("servizi.id"))
    inizio = Column(DateTime, index=True)
    fine = Column(DateTime, index=True)

    utente = relationship("Utente")
    servizio = relationship("Servizio")

engine = create_engine("sqlite:///./appuntamenti.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)