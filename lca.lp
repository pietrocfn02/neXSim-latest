% Facts are injected programmatically and are of the form:
% isa(c1, c2).
% seed(e).      % For each e in a given unit U

isa(X,Z) :- isa(X,Y), isa(Y,Z).
entity(X) :- isa(X,_).
entity(Y) :- isa(_,Y).
notAncestor(E) :- seed(S), entity(E), not isa(S,E).
common(E) :- entity(E), not notAncestor(E).
equiv(X,Y) :- isa(X,Y), isa(Y,X).
noLeastCommon(E) :- common(E), isa(C,E), common(C), not equiv(C,E).
leastCommon(X) :- common(X), not noLeastCommon(X).