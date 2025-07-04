from sqlalchemy import create_engine
from models import Base

DATABASE_URL = "postgresql://quantsim:quantsim123@localhost/quantsim"
engine = create_engine(DATABASE_URL, echo=True)

if __name__ == "__main__":
    Base.metadata.create_all(engine)