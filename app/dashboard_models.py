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




class DashboardWidget(Base):

    __tablename__ = "dashboard_widgets"

    id = Column(Integer, primary_key=True)
    dashboard_id = Column(Integer)

    chart_type = Column(String)
    config_json = Column(String)

    pos_x = Column(String)
    pos_y= Column(String)

    width = Column(String)
    height = Column(String)