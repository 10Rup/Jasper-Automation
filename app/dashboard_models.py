from sqlalchemy import Column, Integer, String
from app.database import Base



class DashboardChart(Base):

    __tablename__ = "dashboard_charts"

    id = Column(Integer, primary_key=True)

    title = Column(String)

    chart_type = Column(String)

    table_name = Column(String)

    x_axis = Column(String)

    y_axis = Column(String)