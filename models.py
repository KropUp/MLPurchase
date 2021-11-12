from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Float, ForeignKey, Date

Base = declarative_base()

class Purchase(Base):
    __tablename__ = 'purchases'

    regNumber = Column(String, primary_key=True)
    name = Column(String)
    max_price = Column(Float)
    currency = Column(String)
    update_dt = Column(Date)
    code = Column(String)

    def __repr__(self):
        return "<Purchase(name='%s', regNumber='%s')>" % (self.name, self.id)

class Company(Base):
    __tablename__ = 'companies'

    inn = Column(String, primary_key=True)
    name = Column(String)

class CompanyAttribute(Base):
    __tablename__ = 'company_attributes'

    id = Column(Integer, primary_key=True)
    company_inn = Column(String, ForeignKey("companies.inn"), nullable=False)
    attribute_type = Column(String, nullable=False)
    attribute_value = Column(String, nullable=False)

class Contract(Base):
    __tablename__ = 'contracts'

    reestrNumber = Column(String, primary_key=True)
    purchase = Column(String, ForeignKey("purchases.regNumber"))
    price = Column(Float)
    customer = Column(String, ForeignKey("companies.inn"), nullable=False)
    executor = Column(String, ForeignKey("companies.inn"), nullable=False)


