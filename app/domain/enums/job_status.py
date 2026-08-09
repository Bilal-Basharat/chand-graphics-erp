from enum import Enum


class JobStatus(str, Enum):
    DRAFT = "DRAFT"
    IN_PRODUCTION = "IN_PRODUCTION"
    COMPLETED = "COMPLETED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


CANCELLABLE = (JobStatus.DRAFT, JobStatus.IN_PRODUCTION)
"""Work that has not been finished can still be called off.

Cancelling puts the materials back on the shelf and the money back in the
customer's hand. Once a job is completed those materials are spent, and
once it is delivered the customer has the work — so neither can be
cancelled without the stock figures becoming a claim that is not true.
Those need a stock return or a write-off, which is a movement of its own.

Lives here rather than in the use case that enforces it, so the list
screen greys the button on exactly the jobs the use case would refuse.
"""
