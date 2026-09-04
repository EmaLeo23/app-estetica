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
    num_operatrici = Column(Integer, default=2)
    logo_url = Column(String, default="https://scontent-fco2-1.xx.fbcdn.net/v/t39.30808-6/480468931_1189319156532944_8943714481012053854_n.jpg?stp=dst-jpg_tt6&cstp=mx1003x650&ctp=s1003x650&_nc_cat=111&ccb=1-7&_nc_sid=cc71e4&_nc_ohc=Fs2-WrR3-dkQ7kNvwEHzcjC&_nc_oc=AdqdyOXfzHmLML8Ur_2BKaJ2MXnaniHnElnNPmnYIPvMflL7NKfefU_6iWlSFbqVPYo&_nc_zt=23&_nc_ht=scontent-fco2-1.xx&_nc_gid=TVdK4anBsl2p24uHROhXOg&_nc_ss=7b289&oh=00_AQI-8iwrNJSMIV_v-oFRdCRfyHTayEJuBV_4VkrDndz2uw&oe=6AA0784C")
    # Memorizziamo la griglia settimanale in formato JSON
    orari_settimana = Column(String, default='{"0":{"aperto":false,"am_a":"","am_c":"","pm_a":"","pm_c":""},"1":{"aperto":false,"am_a":"","am_c":"","pm_a":"","pm_c":""},"2":{"aperto":true,"am_a":"08:30","am_c":"12:30","pm_a":"14:30","pm_c":"19:30"},"3":{"aperto":true,"am_a":"08:30","am_c":"12:30","pm_a":"14:30","pm_c":"19:30"},"4":{"aperto":true,"am_a":"08:30","am_c":"12:30","pm_a":"14:30","pm_c":"19:30"},"5":{"aperto":true,"am_a":"08:30","am_c":"12:30","pm_a":"14:30","pm_c":"19:30"},"6":{"aperto":true,"am_a":"08:30","am_c":"12:30","pm_a":"14:30","pm_c":"19:30"}}')

class Prenotazione(Base):
    __tablename__ = "prenotazioni"
    id = Column(Integer, primary_key=True, index=True)
    utente_id = Column(Integer, ForeignKey("utenti.id"))
    servizio_id = Column(Integer, ForeignKey("servizi.id"))
    inizio = Column(DateTime, index=True)
    fine = Column(DateTime, index=True)
    stato = Column(String, default="in_attesa")
    operatrice = Column(String, default="Non Assegnata")

    utente = relationship("Utente")
    servizio = relationship("Servizio")

engine = create_engine("sqlite:///./appuntamenti.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)