from flask import request
from flask_restx import Resource, Api
from pydantic import ValidationError
from neXSim import app
from neXSim.characterization import characterize, kernel_explanation
from neXSim.models import *
from neXSim.search import *
from neXSim.summary import full_summary
from neXSim.lca import lca
from neXSim.report import report_all


api = Api(app, doc='/api/docs', title='neXSim API', version='0.1', description='neXSim API')


def validate_and_parse(json):
    try:
        _input = NeXSimResponse.model_validate(json)
    except ValidationError as e:
        return {"error": e.errors()}, 400

    return _input


def check_summary(req: NeXSimResponse):
    if req.summaries is None:
        return False
    summarized_entities = [x.entity for x in req.summaries]
    for entity in req.unit:
        if entity not in summarized_entities:
            return False

    return True


def check_lca(req: NeXSimResponse):
    return req.lca is not None


@api.route('/index/')
@api.doc()
class Index(Resource):

    @api.response(200, 'Success')
    def get(self):
        return "Welcome to neXSim"


# Receives a list of valid Babelnet ids as a parameter
# Outputs a list of "Entity"
@api.route('/api/entities/<string:ids>')
@api.doc(params={'ids': 'a list of valid babelnet ids separated by comma'})
class Search(Resource):

    @api.response(200, 'Success')
    def get(self, ids):

        from neXSim.utils import is_valid_babelnet_id
        entities = ids.split(',')
        for entity in entities:
            if not is_valid_babelnet_id(entity):
                return app.response_class(
                    response=f"{entity} is not a valid babelnet id",
                    status=400,
                    mimetype='text/plain'
                )

        resp: EntityList = EntityList(entities=list(search_by_id(entities, True)))

        return app.response_class(
            response=(resp.model_dump_json()),
            status=200,
            mimetype='application/json'
        )


# Receives in the body a list of Entity ID (which are Babelnet IDs) [field "unit"]
# Produces a dict, called "summaries", in which, for each "entity",
# we have a list of Relation [field "Summary"]
# and a list of entity IDs [field "tops"]

@api.route('/api/summary')
class Summary(Resource):

    @api.param("humanReadable", "Return results in human-readable format (true/false)",
               type=bool, required=False, default=False)
    @api.response(200, 'Success')
    def post(self):

        parsed_request = validate_and_parse(request.json)

        if type(parsed_request) != NeXSimResponse:
            return parsed_request

        my_request: NeXSimResponse = parsed_request

        if my_request.summaries is None:
            my_request.summaries = []

        full_summary(my_request)

        return app.response_class(
            response=my_request.model_dump_json(),
            status=200,
            mimetype='application/json',
        )


# Essentially the same as "summary"
# But in the output also produces a field called ["lca"] which is essentially a list of Relation
@api.route('/api/lca')
class LCA(Resource):

    @api.response(200, 'Success')
    def post(self):
        parsed_request = validate_and_parse(request.json)

        if type(parsed_request) != NeXSimResponse:
            return parsed_request

        my_request: NeXSimResponse = parsed_request

        if not check_summary(my_request):
            return app.response_class(
                response=f"Unit has no summary. Cannot proceed to the characterization",
                status=400,
                mimetype='text/plain'
            )

        lca(my_request)

        return app.response_class(
            response=my_request.model_dump_json(),
            status=200,
            mimetype='application/json',
        )


@api.route('/api/characterize')
class Characterization(Resource):

    @api.response(200, 'Success')
    def post(self):
        parsed_request = validate_and_parse(request.json)

        if type(parsed_request) != NeXSimResponse:
            return parsed_request

        my_request: NeXSimResponse = parsed_request

        if not check_summary(my_request):
            return app.response_class(
                response=f"Unit has no summary. Cannot proceed to the characterization",
                status=400,
                mimetype='text/plain'
            )

        # Here the computation
        characterize(my_request)

        return app.response_class(
            response=my_request.model_dump_json(),
            status=200,
            mimetype='application/json',
        )


@api.route('/api/kernel')
class Kernel(Resource):

    @api.response(200, 'Success')
    def post(self):
        parsed_request = validate_and_parse(request.json)

        if type(parsed_request) != NeXSimResponse:
            return parsed_request

        my_request: NeXSimResponse = parsed_request

        if not check_summary(my_request):
            return app.response_class(
                response=f"Unit has no summary. Cannot proceed to the characterization",
                status=400,
                mimetype='text/plain'
            )

        if not check_lca(my_request):
            return app.response_class(
                response=f"Unit has no lca. Cannot proceed to the kernel explanation",
                status=400,
                mimetype='text/plain'
            )

        kernel_explanation(my_request)


        return app.response_class(
            response=my_request.model_dump_json(),
            status=200,
            mimetype='application/json',
        )


@api.route('/api/unit/report')
class Report(Resource):
    @api.response(200, 'Success')
    def post(self):
        try:
            _input = NeXSimResponse.model_validate(request.json)
        except ValidationError as e:
            return {"error": e.errors()}, 400

        raw_data = report_all(_input)

        return app.response_class(
            response=raw_data,
            status=200,
            mimetype='text/plain'
        )
