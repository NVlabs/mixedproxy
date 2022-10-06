.PHONY: all clean check test

ALLOYPATH=./alloy
ALLOYJAR=$(ALLOYPATH)/org.alloytools.alloy.dist.jar

CLASSPATH=".:$(ALLOYJAR)"
#JAVAFLAGS=

all: $(ALLOYPATH)/RunAlloy.class

$(ALLOYJAR):
	cd $(ALLOYPATH) && wget https://github.com/AlloyTools/org.alloytools.alloy/releases/download/v5.1.0/org.alloytools.alloy.dist.jar

$(ALLOYPATH)/RunAlloy.class: $(ALLOYPATH)/RunAlloy.java $(ALLOYJAR)
	javac $(JAVAFLAGS) -classpath $(CLASSPATH) $<

clean:
	rm -f $(ALLOYPATH)/*.class

TESTS=$(wildcard tests/*.test)

check:
	parallel -i sh -c "echo {}; ./src/test_to_alloy.py {} > /dev/null || (echo {} failed; exit 1)" -- `ls tests/*.test`

test:
	$(foreach file, $(wildcard src/unittest*.py), \
		python3 $(file) || exit 1; \
	)
