from fastapi import FastAPI, Depends, Form, HTTPException, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from backend.models import Manufacturer, Counterparty
from backend.database import get_db

app = FastAPI()

templates = Jinja2Templates(directory="templates")


@app.get("/manufacturer")
async def manufacturer(request: Request, db: Session = Depends(get_db)):
    manufacturers = db.query(Manufacturer).all()
    return templates.TemplateResponse("manufacturers.html",
                                     {"request": request, "manufacturers": manufacturers})


@app.get("/manufacturer/create")
async def create_manufacturer(request: Request):
    return templates.TemplateResponse("create_manufacturer.html", {"request": request})


@app.post("/manufacturer/create")
async def create_manufacturer_post(name: str = Form(...), address: str = Form(...),
                                   manager: str = Form(...), phone_number: str = Form(...),
                                   db: Session = Depends(get_db)):
    new_manufacturer = Manufacturer(name=name, address=address, manager=manager, phone_number=phone_number)
    db.add(new_manufacturer)
    db.commit()
    return RedirectResponse(url="/manufacturer", status_code=303)


@app.get("/manufacturer/edit/{manufacturer_id}")
async def edit_manufacturer(request: Request, manufacturer_id: int, db: Session = Depends(get_db)):
    manufacturer = db.query(Manufacturer).filter(Manufacturer.id == manufacturer_id).first()
    if manufacturer is None:
        raise HTTPException(status_code=404, detail="Manufacturer not found")
    return templates.TemplateResponse("edit_manufacturer.html",
                                     {"request": request, "manufacturer": manufacturer})


@app.post("/manufacturer/edit/{manufacturer_id}")
async def edit_manufacturer_post(manufacturer_id: int, name: str = Form(...), address: str = Form(...),
                                 manager: str = Form(...), phone_number: str = Form(...),
                                 db: Session = Depends(get_db)):
    manufacturer = db.query(Manufacturer).filter(Manufacturer.id == manufacturer_id).first()
    if manufacturer is None:
        raise HTTPException(status_code=404, detail="Manufacturer not found")

    manufacturer.name = name
    manufacturer.address = address
    manufacturer.manager = manager
    manufacturer.phone_number = phone_number
    db.commit()
    return RedirectResponse(url="/manufacturer", status_code=303)


@app.get("/manufacturer/delete/{manufacturer_id}")
async def delete_manufacturer(manufacturer_id: int, db: Session = Depends(get_db)):
    manufacturer = db.query(Manufacturer).filter(Manufacturer.id == manufacturer_id).first()
    if manufacturer is None:
        raise HTTPException(status_code=404, detail="Manufacturer not found")

    db.delete(manufacturer)
    db.commit()
    return RedirectResponse(url="/manufacturer", status_code=303)

@app.get("/counterparty")
async def counterparty(request: Request, db: Session = Depends(get_db)):
    counterparties = db.query(Counterparty).all()
    return templates.TemplateResponse("counterparties.html", {"request": request, "counterparties": counterparties})


@app.get("/counterparty/create")
async def create_counterparty(request: Request):
    return templates.TemplateResponse("create_counterparty.html", {"request": request})


@app.post("/counterparty/create")
async def create_counterparty_post(
    name: str = Form(...),
    address: str = Form(...),
    phone_number: str = Form(...),
    db: Session = Depends(get_db)
):
    new_counterparty = Counterparty(name=name, address=address, phone_number=phone_number)
    db.add(new_counterparty)
    db.commit()
    return RedirectResponse(url="/counterparty", status_code=303)


@app.get("/counterparty/edit/{counterparty_id}")
async def edit_counterparty(request: Request, counterparty_id: int, db: Session = Depends(get_db)):
    counterparty = db.query(Counterparty).filter(Counterparty.id == counterparty_id).first()
    if counterparty is None:
        raise HTTPException(status_code=404, detail="Counterparty not found")
    return templates.TemplateResponse("edit_counterparty.html", {"request": request, "counterparty": counterparty})


@app.post("/counterparty/edit/{counterparty_id}")
async def edit_counterparty_post(
    counterparty_id: int,
    name: str = Form(...),
    address: str = Form(...),
    phone_number: str = Form(...),
    db: Session = Depends(get_db)
):
    counterparty = db.query(Counterparty).filter(Counterparty.id == counterparty_id).first()
    if counterparty is None:
        raise HTTPException(status_code=404, detail="Counterparty not found")

    counterparty.name = name
    counterparty.address = address
    counterparty.phone_number = phone_number
    db.commit()
    return RedirectResponse(url="/counterparty", status_code=303)


@app.get("/counterparty/delete/{counterparty_id}")
async def delete_counterparty(counterparty_id: int, db: Session = Depends(get_db)):
    counterparty = db.query(Counterparty).filter(Counterparty.id == counterparty_id).first()
    if counterparty is None:
        raise HTTPException(status_code=404, detail="Counterparty not found")

    db.delete(counterparty)
    db.commit()
    return RedirectResponse(url="/counterparty", status_code=303)