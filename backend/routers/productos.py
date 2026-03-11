from fastapi import APIRouter, File, HTTPException
from models import Producto
from database import get_db
from sqlalchemy.orm import Session
from fastapi import Depends

router = APIRouter(prefix="/productos", tags=["productos"])

@router.get("/")
def obtener_productos(categoria: str = None, db: Session = Depends(get_db)):
    """Obtiene todos los productos, opcionalmente filtrando por categoría"""
    if categoria:
        productos = db.query(Producto).filter(Producto.categoria == categoria).all()
        if not productos:
            raise HTTPException(status_code=404, detail="Categoría no encontrada")
    else:
        productos = db.query(Producto).all()
    return [{
        "id": producto.id,
        "nombre": producto.nombre,
        "categoria": producto.categoria,
        "precio_venta": producto.precio_venta,
        "stock_actual": producto.stock_actual,
        "stock_minimo": producto.stock_minimo,
        "unidad": producto.unidad
        } for producto in productos]

@router.get("/{id}")
def obtener_producto(id: int, db: Session = Depends(get_db)):
    """Obtiene un producto por su ID"""
    producto = db.query(Producto).filter(Producto.id == id).first()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return {
        "id": producto.id,
        "nombre": producto.nombre,
        "categoria": producto.categoria,
        "precio_venta": producto.precio_venta,
        "stock_actual": producto.stock_actual,
        "stock_minimo": producto.stock_minimo,
        "unidad": producto.unidad
    }
    
@router.post("/")
def crear_producto(producto: Producto, db: Session = Depends(get_db)):
    """Crea un nuevo producto"""
    nuevo_producto = Producto(nombre=producto.nombre, categoria=producto.categoria, precio_venta=producto.precio_venta, stock_actual=producto.stock_actual, stock_minimo=producto.stock_minimo, unidad=producto.unidad)
    db.add(nuevo_producto)
    db.commit()
    db.refresh(nuevo_producto)
    return {
        "estado": "OK",
        "id": nuevo_producto.id,
        "nombre": nuevo_producto.nombre,
        "categoria": nuevo_producto.categoria,
        "precio_venta": nuevo_producto.precio_venta,
        "stock_actual": nuevo_producto.stock_actual,
        "stock_minimo": nuevo_producto.stock_minimo,
        "unidad": nuevo_producto.unidad
    }
    
@router.patch("/{id}")
def actualizar_producto(id: int, producto: Producto, db: Session = Depends(get_db)):
    """Actualiza un producto existente"""
    producto_existente = db.query(Producto).filter(Producto.id == id).first()
    if not producto_existente:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    producto_existente.nombre = producto.nombre
    producto_existente.categoria = producto.categoria
    producto_existente.precio_venta = producto.precio_venta
    producto_existente.stock_actual = producto.stock_actual
    producto_existente.stock_minimo = producto.stock_minimo
    producto_existente.unidad = producto.unidad
    db.commit()
    db.refresh(producto_existente)
    
    return {
        "estado": "OK",
        "id": producto_existente.id,
        "nombre": producto_existente.nombre,
        "categoria": producto_existente.categoria,
        "precio_venta": producto_existente.precio_venta,
        "stock_actual": producto_existente.stock_actual,
        "stock_minimo": producto_existente.stock_minimo,
        "unidad": producto_existente.unidad
    }
    
@router.delete("/{id}")
def eliminar_producto(id: int, db: Session = Depends(get_db)):
    """Elimina un producto existente, si no tiene ventas asociadas"""
    producto_existente = db.query(Producto).filter(Producto.id == id).first()
    if not producto_existente:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    if producto_existente.ventas > 0:
        raise HTTPException(status_code=400, detail="Producto tiene ventas asociadas, no se puede eliminar")
    db.delete(producto_existente)
    db.commit()

    return {
        "estado": "OK",
        "id": id
    }
    
@router.get("/alertas")
def obtener_alertas(db: Session = Depends(get_db)):
    """Obtiene las alertas de los productos"""
    alertas = db.query(Producto).filter(Producto.stock_actual < Producto.stock_minimo).all()
    return [{
        "id": alerta.id,
        "nombre": alerta.nombre,
        "stock_actual": alerta.stock_actual,
        "stock_minimo": alerta.stock_minimo
    } for alerta in alertas ]