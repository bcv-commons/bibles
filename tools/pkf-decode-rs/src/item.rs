//! Item shape shared by unsuccinctify.rs and render.rs — mirrors the Python
//! port's `['token'|'scope'|'graft', sub, payload]` tuples.

#[derive(Clone, Debug)]
pub enum Item {
    Token { sub: String, payload: String },
    ScopeStart { payload: String },
    ScopeEnd { payload: String },
    Graft { sub: String, payload: String },
}
