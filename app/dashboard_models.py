from sqlalchemy import Column, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from app.database import Base


class Dashboard(Base):

    __tablename__ = "dashboard"

    id = Column(Integer, primary_key=True)

    name = Column(String)

    



class DashboardChart(Base):

    __tablename__ = "dashboard_charts"

    id = Column(Integer, primary_key=True)

    title = Column(String)

    chart_type = Column(String)

    table_name = Column(String)

    x_axis = Column(String)

    y_axis = Column(String)




class DashboardWidget(Base):

    __tablename__ = "dashboard_widgets"

    id = Column(Integer, primary_key=True)
    dashboard_id = Column(Integer)

    chart_type = Column(String)
    config_json = Column(JSONB)

    pos_x = Column(String)
    pos_y= Column(String)

    width = Column(String)
    height = Column(String)